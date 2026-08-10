#!/usr/bin/env python3
"""
Evidence bundle collector for k8s-ai-troubleshooter.

Runs the read-only diagnostic command set against a cluster, redacts the output,
and writes a structured bundle an AI assistant can analyse in one pass.

This exists because the two most common ways to use this repository are both
awkward without it:

- an assistant with terminal access issues commands one at a time, spending a
  turn per `kubectl` call and re-deriving context each time;
- an assistant *without* terminal access (a browser chat) needs the operator to
  paste output by hand, which is where unredacted secrets get published.

Both are solved by collecting once, redacting once, and handing over a bundle.

Two integrity properties, both enforced in code rather than by convention:

1. **Every command is classified before it runs.** Each is passed through
   `scripts/safety.py` and refused unless it lands in `SAFE_READ` or
   `SAFE_DIAGNOSTIC`. The collector cannot mutate a cluster even if someone adds
   a bad entry to the plan, and `tests/test_collect.py` asserts the whole plan
   classifies safe.

2. **Every captured file is redacted before it is written.** Output goes through
   `scripts/redact.py` on the way to disk, so an unredacted secret is never
   persisted in the first place.
"""

import argparse
import datetime
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from redact import redact  # noqa: E402
from safety import SAFE_DIAGNOSTIC, SAFE_READ, classify  # noqa: E402

ALLOWED_TIERS = {SAFE_READ, SAFE_DIAGNOSTIC}

#: Commands that describe the cluster as a whole. `{ns_flag}` expands to
#: `-n <namespace>` or `--all-namespaces`.
CLUSTER_PLAN = [
    ("cluster-info", "kubectl cluster-info"),
    ("version", "kubectl version -o json"),
    ("nodes", "kubectl get nodes -o wide"),
    ("nodes-detail", "kubectl describe nodes"),
    ("api-resources", "kubectl api-resources --verbs=list -o name"),
    ("namespaces", "kubectl get namespaces"),
    ("storageclasses", "kubectl get storageclass -o wide"),
    ("persistentvolumes", "kubectl get pv -o wide"),
]

#: Commands scoped to the namespace under investigation.
NAMESPACE_PLAN = [
    ("pods", "kubectl get pods {ns_flag} -o wide"),
    ("pods-yaml", "kubectl get pods {ns_flag} -o yaml"),
    ("events", "kubectl get events {ns_flag} --sort-by=.lastTimestamp"),
    ("deployments", "kubectl get deployments {ns_flag} -o wide"),
    ("replicasets", "kubectl get replicasets {ns_flag} -o wide"),
    ("statefulsets", "kubectl get statefulsets {ns_flag} -o wide"),
    ("daemonsets", "kubectl get daemonsets {ns_flag} -o wide"),
    ("jobs", "kubectl get jobs {ns_flag} -o wide"),
    ("cronjobs", "kubectl get cronjobs {ns_flag} -o wide"),
    ("services", "kubectl get services {ns_flag} -o wide"),
    ("endpoints", "kubectl get endpoints {ns_flag}"),
    ("ingress", "kubectl get ingress {ns_flag} -o wide"),
    ("networkpolicies", "kubectl get networkpolicies {ns_flag}"),
    ("pvc", "kubectl get pvc {ns_flag} -o wide"),
    ("configmaps", "kubectl get configmaps {ns_flag}"),
    ("secrets-metadata", "kubectl get secrets {ns_flag}"),
    ("resourcequotas", "kubectl get resourcequota {ns_flag} -o yaml"),
    ("limitranges", "kubectl get limitrange {ns_flag} -o yaml"),
    ("hpa", "kubectl get hpa {ns_flag} -o wide"),
    ("pdb", "kubectl get poddisruptionbudget {ns_flag}"),
]

#: Best-effort extras. Absent metrics-server or Helm is normal, not an error.
OPTIONAL_PLAN = [
    ("top-nodes", "kubectl top nodes"),
    ("top-pods", "kubectl top pods {ns_flag}"),
    ("helm-releases", "helm list --all-namespaces"),
]

#: Per-failing-pod follow-ups. `{pod}` and `{ns}` are substituted per pod.
POD_PLAN = [
    ("describe", "kubectl describe pod {pod} -n {ns}"),
    ("logs", "kubectl logs {pod} -n {ns} --all-containers --tail=200"),
    ("logs-previous", "kubectl logs {pod} -n {ns} --all-containers --previous --tail=200"),
]

#: Pod states worth pulling logs for.
UNHEALTHY_MARKERS = (
    "CrashLoopBackOff", "Error", "ImagePullBackOff", "ErrImagePull", "Pending",
    "Evicted", "OOMKilled", "CreateContainerConfigError", "InvalidImageName",
    "ContainerCreating", "Init:Error", "Init:CrashLoopBackOff", "Terminating",
    "RunContainerError", "CreateContainerError", "NodeAffinity", "Unknown",
)


class UnsafeCommand(RuntimeError):
    """Raised when a planned command does not classify as read-only."""


def assert_safe(command):
    """Classify `command` and raise unless it is read-only."""
    verdict = classify(command)
    if verdict.safety not in ALLOWED_TIERS:
        raise UnsafeCommand(
            f"refusing to run {command!r}: classified {verdict.safety} ({verdict.reason})"
        )
    return verdict


def build_plan(namespace=None, all_namespaces=False, include_optional=True):
    """Return [(name, command)] for the cluster-wide and namespaced steps."""
    if all_namespaces:
        ns_flag = "--all-namespaces"
    elif namespace:
        ns_flag = f"-n {namespace}"
    else:
        ns_flag = ""

    plan = list(CLUSTER_PLAN)
    plan += [(name, tpl.format(ns_flag=ns_flag).strip()) for name, tpl in NAMESPACE_PLAN]
    if include_optional:
        plan += [(name, tpl.format(ns_flag=ns_flag).strip()) for name, tpl in OPTIONAL_PLAN]
    return plan


def run_command(command, timeout=60):
    """Run a read-only command, returning (ok, output). Never raises on failure."""
    assert_safe(command)
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return False, f"[collector] command timed out after {timeout}s: {command}"
    except OSError as exc:
        return False, f"[collector] could not execute: {exc}"

    output = result.stdout
    if result.returncode != 0:
        output = (output + "\n" + result.stderr).strip()
        output = f"[collector] exit={result.returncode}\n{output}"
    return result.returncode == 0, output


def _pod_status_reasons(pod):
    """Collect every waiting/terminated reason and the top-level status reason."""
    status = pod.get("status", {}) or {}
    reasons = []
    if status.get("reason"):
        reasons.append(status["reason"])

    for key in ("initContainerStatuses", "containerStatuses"):
        for cs in status.get(key) or []:
            state = cs.get("state") or {}
            waiting = state.get("waiting") or {}
            if waiting.get("reason"):
                reasons.append(waiting["reason"])
            terminated = state.get("terminated") or {}
            term_reason = terminated.get("reason")
            if term_reason and (terminated.get("exitCode", 0) != 0 or term_reason != "Completed"):
                reasons.append(term_reason)
    return reasons


def _pod_is_unhealthy(pod):
    """
    True if `pod` (a decoded `kubectl get pod -o json` item) is not healthy.

    Mirrors the same states scripts/collect.py's UNHEALTHY_MARKERS and
    symptom-index.yaml already key decisions on, read directly from the
    structured fields those decisions are actually made from, rather than
    from kubectl's rendered STATUS/READY columns.
    """
    metadata = pod.get("metadata", {}) or {}
    status = pod.get("status", {}) or {}
    phase = status.get("phase", "Unknown")

    if phase == "Succeeded":
        return False
    if phase in ("Pending", "Failed", "Unknown"):
        return True
    if metadata.get("deletionTimestamp"):
        return True  # Terminating

    if any(reason in UNHEALTHY_MARKERS for reason in _pod_status_reasons(pod)):
        return True

    if phase == "Running":
        container_statuses = status.get("containerStatuses") or []
        if container_statuses and not all(cs.get("ready") for cs in container_statuses):
            return True  # Running but not fully Ready — hidden by STATUS alone

    return False


def find_unhealthy_pods(namespace=None, all_namespaces=False):
    """
    Return [(namespace, pod)] for pods that are not healthy.

    Reads pod JSON rather than parsing kubectl's printed STATUS/READY columns.
    That column text is not a stable API — it has changed across kubectl
    versions and varies with custom printer columns — while `status.phase`,
    `containerStatuses[].ready`, and the waiting/terminated `reason` fields are
    the same structured source every other decision in this project already
    keys on (symptom-index.yaml, docs/reference/pod-states.md).
    """
    if all_namespaces:
        command = "kubectl get pods --all-namespaces -o json"
    elif namespace:
        command = f"kubectl get pods -n {namespace} -o json"
    else:
        command = "kubectl get pods -o json"

    ok, output = run_command(command)
    if not ok:
        return []

    try:
        payload = json.loads(output)
    except json.JSONDecodeError:
        return []

    pods = []
    for pod in payload.get("items", []):
        if not _pod_is_unhealthy(pod):
            continue
        metadata = pod.get("metadata", {}) or {}
        name = metadata.get("name")
        ns = metadata.get("namespace") or namespace or "default"
        if name:
            pods.append((ns, name))
    return pods


def write_capture(out_dir, name, command, output):
    """Redact `output` and write it to the bundle. Returns redaction stats."""
    redacted, stats = redact(output)
    header = f"$ {command}\n{'=' * 72}\n"
    (out_dir / f"{name}.txt").write_text(header + redacted + "\n", encoding="utf-8")
    return stats


def collect(out_dir, namespace=None, all_namespaces=False, include_optional=True,
            include_pods=True, timeout=60, log=print):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    totals = {}
    failed = []

    def record(stats):
        for kind, count in stats.items():
            totals[kind] = totals.get(kind, 0) + count

    for name, command in build_plan(namespace, all_namespaces, include_optional):
        ok, output = run_command(command, timeout=timeout)
        if not ok:
            failed.append(name)
        record(write_capture(out_dir, name, command, output))
        log(f"  {'ok ' if ok else 'err'}  {name}")

    if include_pods:
        pods_dir = out_dir / "pods"
        pods_dir.mkdir(exist_ok=True)
        unhealthy = find_unhealthy_pods(namespace, all_namespaces)
        log(f"  unhealthy pods: {len(unhealthy)}")
        for ns, pod in unhealthy:
            for suffix, template in POD_PLAN:
                command = template.format(pod=pod, ns=ns)
                ok, output = run_command(command, timeout=timeout)
                record(write_capture(pods_dir, f"{ns}_{pod}_{suffix}", command, output))

    manifest = [
        "# Evidence Bundle",
        "",
        f"- Collected: {datetime.datetime.now(datetime.timezone.utc).isoformat()}",
        f"- Scope: {'all namespaces' if all_namespaces else (namespace or 'current namespace')}",
        f"- Commands that returned an error: {', '.join(failed) if failed else 'none'}",
        "",
        "## Redaction summary",
        "",
    ]
    if totals:
        manifest += [f"- `{kind}`: {count} value(s) redacted" for kind, count in sorted(totals.items())]
    else:
        manifest.append("- Nothing matched a redaction rule.")
    manifest += [
        "",
        "Values are replaced with `[REDACTED:<kind>:<fingerprint>]`. The fingerprint",
        "is the first 8 hex characters of the SHA-256 of the original value, so",
        "identical secrets share a fingerprint and can be correlated across files",
        "without being revealed.",
        "",
        "Redaction is best effort. Review this bundle before sharing it.",
        "",
        "## How to use this bundle",
        "",
        "Hand the whole directory to an assistant configured per",
        "`docs/usage/`, and start from `runbooks/triage.md`.",
        "",
    ]
    (out_dir / "README.md").write_text("\n".join(manifest), encoding="utf-8")
    return totals, failed


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Collect a redacted, read-only Kubernetes evidence bundle for AI analysis.",
    )
    parser.add_argument("-n", "--namespace", help="Namespace to investigate.")
    parser.add_argument("-A", "--all-namespaces", action="store_true",
                        help="Collect across every namespace.")
    parser.add_argument("-o", "--output", default="evidence-bundle",
                        help="Output directory (default: evidence-bundle).")
    parser.add_argument("--no-pods", action="store_true",
                        help="Skip per-pod describe and logs.")
    parser.add_argument("--no-optional", action="store_true",
                        help="Skip kubectl top and helm list.")
    parser.add_argument("--timeout", type=int, default=60,
                        help="Per-command timeout in seconds (default: 60).")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the command plan and its safety classification, run nothing.")
    args = parser.parse_args(argv)

    plan = build_plan(args.namespace, args.all_namespaces, not args.no_optional)

    if args.dry_run:
        print(f"{'TIER':<16} COMMAND")
        for _, command in plan:
            print(f"{classify(command).safety:<16} {command}")
        for _, template in POD_PLAN:
            command = template.format(pod="<pod>", ns="<namespace>")
            print(f"{classify(command).safety:<16} {command}")
        return 0

    if not shutil.which("kubectl"):
        print("kubectl not found on PATH.", file=sys.stderr)
        return 2

    print(f"Collecting evidence into {args.output}/ ...")
    totals, failed = collect(
        args.output,
        namespace=args.namespace,
        all_namespaces=args.all_namespaces,
        include_optional=not args.no_optional,
        include_pods=not args.no_pods,
        timeout=args.timeout,
    )

    print(f"\nBundle written to {Path(args.output).resolve()}")
    if totals:
        summary = ", ".join(f"{kind}={count}" for kind, count in sorted(totals.items()))
        print(f"Redacted: {summary}")
    else:
        print("Redacted: nothing matched a redaction rule.")
    if failed:
        print(f"Commands that errored (often normal): {', '.join(failed)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
