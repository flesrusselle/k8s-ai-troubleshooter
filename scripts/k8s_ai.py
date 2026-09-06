#!/usr/bin/env python3
"""Unified CLI for the k8s-ai-troubleshooter read-only workflows."""

import argparse
import json
import sys
import tarfile
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(REPO_ROOT))

import collect  # noqa: E402
import session_log  # noqa: E402
from k8s_ai_core import investigate_bundle  # noqa: E402
from k8s_ai_core.investigation import DEFAULT_SPIKE_THRESHOLD  # noqa: E402
from notify import SUPPORTED_TARGETS, build_payload, resolve_url, send_alert  # noqa: E402
from safety import SAFE_DIAGNOSTIC, SAFE_READ, classify  # noqa: E402

VERSION = "0.2.0"
ALLOWED_AUTOMATIC_TIERS = {SAFE_READ, SAFE_DIAGNOSTIC}


def _add_collection_arguments(parser):
    parser.add_argument("--namespace", help="Namespace to investigate.")
    parser.add_argument("--all-namespaces", action="store_true",
                        help="Collect across every namespace.")
    parser.add_argument("--output", default="evidence-bundle",
                        help="Output directory (default: evidence-bundle).")
    parser.add_argument("--no-pods", action="store_true",
                        help="Skip per-pod describe and logs.")
    parser.add_argument("--no-optional", action="store_true",
                        help="Skip kubectl top and helm list.")
    parser.add_argument("--timeout", type=int, default=60,
                        help="Per-command timeout in seconds (default: 60).")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the plan and safety classifications without running it.")
    parser.add_argument("--spike-check", action="store_true",
                        help="After collection, run resource spike analysis on the bundle.")


def _add_notify_arguments(parser):
    """Shared webhook arguments used by 'notify' and 'triage --notify-webhook'."""
    parser.add_argument("--notify-webhook", metavar="URL",
                        help="Webhook URL to POST alert to if high-confidence findings exist.")
    parser.add_argument("--notify-target", choices=SUPPORTED_TARGETS, default="slack",
                        help="Alert target (default: slack).")
    parser.add_argument("--notify-dry-run", action="store_true",
                        help="Print the webhook payload without sending it.")


def build_parser():
    parser = argparse.ArgumentParser(
        add_help=False,
        prog="k8s-ai",
        description="Read-only Kubernetes investigation and evidence tools.",
    )
    parser.add_argument("--help", action="help", help="Show this help message and exit.")
    parser.add_argument("--version", action="version", version=f"k8s-ai {VERSION}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # ── collect ──────────────────────────────────────────────────────────────
    collect_parser = subparsers.add_parser(
        "collect", help="Collect a redacted, read-only evidence bundle.",
        add_help=False,
    )
    collect_parser.add_argument("--help", action="help", help="Show this help message and exit.")
    _add_collection_arguments(collect_parser)
    collect_parser.add_argument("--spike-threshold", type=int, default=DEFAULT_SPIKE_THRESHOLD,
                                metavar="PCT",
                                help=f"Spike detection threshold %% (default: {DEFAULT_SPIKE_THRESHOLD}).")

    # ── safety ───────────────────────────────────────────────────────────────
    safety_parser = subparsers.add_parser(
        "safety", help="Classify a command before considering execution.",
        add_help=False,
    )
    safety_parser.add_argument("--help", action="help", help="Show this help message and exit.")
    safety_parser.add_argument("command_text", help="Command string to classify.")
    safety_parser.add_argument("--json", action="store_true",
                               help="Print the verdict as JSON.")

    # ── sessions ─────────────────────────────────────────────────────────────
    sessions_parser = subparsers.add_parser(
        "sessions", help="Review recorded investigation and collection sessions.",
        add_help=False,
    )
    sessions_parser.add_argument("--help", action="help", help="Show this help message and exit.")
    sessions_parser.add_argument("--tail", type=int, metavar="N",
                                 help="Print the last N entries.")
    sessions_parser.add_argument("--path", action="store_true",
                                 help="Print the resolved session log path.")
    sessions_parser.add_argument("--json", action="store_true",
                                 help="Print selected entries as JSON.")

    # ── investigate ──────────────────────────────────────────────────────────
    investigate_parser = subparsers.add_parser(
        "investigate", help="Analyze a previously collected evidence bundle.",
        add_help=False,
    )
    investigate_parser.add_argument("--help", action="help", help="Show this help message and exit.")
    investigate_parser.add_argument("question", nargs="?", default="Investigate the evidence bundle",
                                    help="Question to answer.")
    investigate_parser.add_argument("--bundle", default="evidence-bundle",
                                    help="Evidence bundle directory (default: evidence-bundle).")
    investigate_parser.add_argument("--json", action="store_true",
                                    help="Print the structured report as JSON.")
    investigate_parser.add_argument("--spike-threshold", type=int, default=DEFAULT_SPIKE_THRESHOLD,
                                    metavar="PCT",
                                    help=f"Spike detection threshold %% (default: {DEFAULT_SPIKE_THRESHOLD}).")

    # ── triage ───────────────────────────────────────────────────────────────
    triage_parser = subparsers.add_parser(
        "triage",
        help="Collect evidence (if needed), investigate, and render a full triage report.",
        add_help=False,
    )
    triage_parser.add_argument("--help", action="help", help="Show this help message and exit.")
    triage_parser.add_argument("question", nargs="?", default="Investigate the evidence bundle",
                               help="Question to answer.")
    triage_parser.add_argument("--bundle", default="evidence-bundle",
                               help="Evidence bundle directory to investigate (default: evidence-bundle).")
    triage_parser.add_argument("--collect-first", action="store_true",
                               help="Run collection into --bundle before investigating.")
    triage_parser.add_argument("--json", action="store_true",
                               help="Print full InvestigationReport as JSON.")
    triage_parser.add_argument("--spike-threshold", type=int, default=DEFAULT_SPIKE_THRESHOLD,
                               metavar="PCT",
                               help=f"Spike detection threshold %% (default: {DEFAULT_SPIKE_THRESHOLD}).")
    _add_collection_arguments(triage_parser)
    _add_notify_arguments(triage_parser)

    # ── export ───────────────────────────────────────────────────────────────
    export_parser = subparsers.add_parser(
        "export",
        help="Archive an evidence bundle (raw files + triage report) to a .tar.gz.",
        add_help=False,
    )
    export_parser.add_argument("--help", action="help", help="Show this help message and exit.")
    export_parser.add_argument("--bundle", default="evidence-bundle",
                               help="Evidence bundle directory (default: evidence-bundle).")
    export_parser.add_argument("--output", default="",
                               help="Output .tar.gz path (default: <bundle>.tar.gz).")
    export_parser.add_argument("--spike-threshold", type=int, default=DEFAULT_SPIKE_THRESHOLD,
                               metavar="PCT",
                               help=f"Spike threshold %% for included triage report (default: {DEFAULT_SPIKE_THRESHOLD}).")

    # ── notify ───────────────────────────────────────────────────────────────
    notify_parser = subparsers.add_parser(
        "notify", help="Dispatch an alert from a recorded session to Slack, PagerDuty, or Google Chat.",
        add_help=False,
    )
    notify_parser.add_argument("--help", action="help", help="Show this help message and exit.")
    notify_parser.add_argument("--session-id", metavar="UUID",
                               help="Session ID to dispatch. Defaults to the most recent session.")
    notify_parser.add_argument("--target", choices=SUPPORTED_TARGETS, default="slack",
                               help="Alert target (default: slack).")
    notify_parser.add_argument("--webhook", metavar="URL",
                               help="Webhook URL. Falls back to K8S_AI_NOTIFY_<TARGET>_URL env var.")
    notify_parser.add_argument("--dry-run", action="store_true",
                               help="Print the payload without sending.")

    return parser


# ── Command handlers ────────────────────────────────────────────────────────────

def _safety_payload(command):
    verdict = classify(command)
    return {
        "command": command,
        "safety": verdict.safety,
        "reason": verdict.reason,
        "automatic_execution_allowed": verdict.safety in ALLOWED_AUTOMATIC_TIERS,
    }


def _run_safety(args):
    payload = _safety_payload(args.command_text)
    if args.json:
        print(json.dumps(payload, sort_keys=True))
    else:
        print(f"Safety: {payload['safety']}")
        print(f"Automatic execution: {'yes' if payload['automatic_execution_allowed'] else 'no'}")
        print(f"Reason: {payload['reason']}")
    return 0


def _run_sessions(args):
    if args.path:
        print(session_log.log_path())
        return 0

    entries = session_log.read_entries()
    selected = entries[-args.tail:] if args.tail else entries
    if args.json:
        print(json.dumps(selected, sort_keys=True))
    elif args.tail:
        for entry in selected:
            print(json.dumps(entry, sort_keys=True))
    else:
        print(session_log.summarize(entries))
    return 0


def _run_collect(args):
    import os
    collect_args = []
    if args.namespace:
        collect_args += ["--namespace", args.namespace]
    if args.all_namespaces:
        collect_args.append("--all-namespaces")
    collect_args += ["--output", args.output, "--timeout", str(args.timeout)]
    if args.no_pods:
        collect_args.append("--no-pods")
    if args.no_optional:
        collect_args.append("--no-optional")
    if args.dry_run:
        collect_args.append("--dry-run")

    rc = collect.main(collect_args)

    # Spike analysis (post-collect, if requested)
    if rc == 0 and getattr(args, "spike_check", False) and not args.dry_run:
        from k8s_ai_core import detect_spikes
        threshold = getattr(args, "spike_threshold", None) \
            or int(os.environ.get("K8S_AI_SPIKE_THRESHOLD", DEFAULT_SPIKE_THRESHOLD))
        spikes = detect_spikes(Path(args.output), threshold=threshold)
        if spikes:
            print(f"\n⚡ Resource spikes detected (>{threshold}% of limit):")
            for s in spikes:
                print(f"  [{s.severity}] {s.namespace}/{s.pod}/{s.container} "
                      f"{s.resource.upper()}: {s.usage_raw} / {s.limit_raw} ({s.usage_pct}%)")
        else:
            print(f"\n✓ No resource spikes above {threshold}% found.")
    return rc


def _print_report(report):
    """Human-friendly terminal rendering of an InvestigationReport."""
    width = 72
    sep = "─" * width

    print(f"\n{'═' * width}")
    print(f"  k8s-ai triage report")
    print(f"{'═' * width}")
    print(f"  Status  : {report.status}")
    print(f"  Question: {report.question}")
    print(f"  Bundle  : {report.bundle}")
    print(f"{'═' * width}\n")

    if report.hypotheses:
        print("HYPOTHESES")
        print(sep)
        for h in report.hypotheses:
            bar_filled = {"HIGH": "████████", "MEDIUM": "█████   ", "LOW": "███     "}.get(h.confidence, "???")
            print(f"  [{h.confidence:6}] {bar_filled}  {h.title}")
            print(f"           {h.rationale}")
            for ev in h.evidence[:2]:
                print(f"           └─ {ev.source}: {ev.fact}")
            print()

    if report.resource_spikes:
        print("RESOURCE SPIKES")
        print(sep)
        for s in report.resource_spikes:
            badge = "🔴" if s.severity == "HIGH" else "🟡"
            print(f"  {badge} [{s.severity}] {s.namespace}/{s.pod}/{s.container}")
            print(f"       {s.resource.upper()}: {s.usage_raw} / {s.limit_raw} ({s.usage_pct}%)")
        print()

    if report.recommendations:
        print("RECOMMENDATIONS")
        print(sep)
        for i, r in enumerate(report.recommendations, 1):
            print(f"  {i}. {r.action}")
            print(f"     Risk      : {r.risk}")
            print(f"     Verify    : {r.verification}")
            print()

    if report.unknowns:
        print("UNKNOWNS")
        print(sep)
        for u in report.unknowns:
            print(f"  • {u}")
        print()

    print(f"{'═' * width}\n")


def _run_investigate(args):
    threshold = getattr(args, "spike_threshold", DEFAULT_SPIKE_THRESHOLD)
    report = investigate_bundle(args.bundle, args.question, spike_threshold=threshold)
    if args.json:
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
        return 0 if report.status != "UNAVAILABLE" else 2

    _print_report(report)
    return 0 if report.status != "UNAVAILABLE" else 2


def _run_triage(args):
    import os
    # Optionally run collection first
    if getattr(args, "collect_first", False):
        rc = _run_collect(args)
        if rc != 0:
            return rc

    threshold = getattr(args, "spike_threshold", DEFAULT_SPIKE_THRESHOLD)
    report = investigate_bundle(args.bundle, args.question, spike_threshold=threshold)

    if args.json:
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    else:
        _print_report(report)

    # Optionally dispatch notification for high-confidence findings
    if getattr(args, "notify_webhook", None) or resolve_url(args.notify_target) or getattr(args, "notify_dry_run", False):
        _dispatch_notification(
            session={"source": "triage", "bundle_path": args.bundle},
            report=report.to_dict(),
            target=args.notify_target,
            url=args.notify_webhook,
            dry_run=args.notify_dry_run,
        )

    return 0 if report.status != "UNAVAILABLE" else 2


def _run_export(args):
    """Package the bundle + triage report into a .tar.gz."""
    bundle = Path(args.bundle)
    if not bundle.is_dir():
        print(f"Error: bundle directory does not exist: {bundle}", file=sys.stderr)
        return 1

    output = args.output or f"{bundle.name}.tar.gz"
    output_path = Path(output)

    # Run investigation to get the triage report
    threshold = getattr(args, "spike_threshold", DEFAULT_SPIKE_THRESHOLD)
    report = investigate_bundle(str(bundle), spike_threshold=threshold)

    # Write triage-report.json into a temp file and include it in the archive
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, prefix="k8s-ai-triage-"
    ) as tmp:
        json.dump(report.to_dict(), tmp, indent=2, sort_keys=True)
        tmp_path = Path(tmp.name)

    try:
        with tarfile.open(output_path, "w:gz") as tar:
            # Add all evidence bundle files under the bundle dir name
            tar.add(bundle, arcname=bundle.name)
            # Add triage report at the root of the archive
            tar.add(tmp_path, arcname="triage-report.json")
    finally:
        tmp_path.unlink(missing_ok=True)

    print(f"✓ Bundle exported: {output_path.resolve()}")
    print(f"  Contents: {bundle.name}/ + triage-report.json")
    spikes = report.resource_spikes
    if spikes:
        print(f"  ⚡ {len(spikes)} resource spike(s) included in report.")
    return 0


def _dispatch_notification(session, report, target, url, dry_run):
    """Build and send (or dry-run) a webhook alert."""
    resolved_url = resolve_url(target, url)
    if not resolved_url and not dry_run:
        print(
            f"Warning: no webhook URL for target '{target}'. "
            f"Set {('K8S_AI_NOTIFY_' + target.upper() + '_URL')} or pass --notify-webhook.",
            file=sys.stderr,
        )
        return

    # Only alert on actionable signals
    high_conf = any(
        h.get("confidence") == "HIGH"
        for h in (report or {}).get("hypotheses", [])
    )
    has_spike = bool((report or {}).get("resource_spikes"))
    if not high_conf and not has_spike and not dry_run:
        return  # no alert needed — don't spam on clean runs

    payload = build_payload(session, report, target=target)
    try:
        send_alert(target, resolved_url or "", payload, dry_run=dry_run)
        if not dry_run:
            print(f"✓ Alert sent to {target}.")
    except RuntimeError as exc:
        print(f"Warning: alert delivery failed: {exc}", file=sys.stderr)


def _run_notify(args):
    entries = session_log.read_entries()
    if not entries:
        print("No sessions recorded yet.", file=sys.stderr)
        return 1

    if args.session_id:
        entry = next((e for e in reversed(entries) if e.get("session_id") == args.session_id), None)
        if entry is None:
            print(f"Session ID not found: {args.session_id}", file=sys.stderr)
            return 1
    else:
        entry = entries[-1]

    resolved_url = resolve_url(args.target, args.webhook)
    if not resolved_url and not args.dry_run:
        env_var = f"K8S_AI_NOTIFY_{args.target.upper()}_URL"
        print(f"Error: no webhook URL for '{args.target}'. Set {env_var} or pass --webhook.", file=sys.stderr)
        return 1

    payload = build_payload(entry, report=None, target=args.target)
    try:
        send_alert(args.target, resolved_url or "", payload, dry_run=args.dry_run)
        if not args.dry_run:
            print(f"✓ Alert dispatched to {args.target}.")
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


# ── Entry point ─────────────────────────────────────────────────────────────────

def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.command == "collect":
        return _run_collect(args)
    if args.command == "safety":
        return _run_safety(args)
    if args.command == "sessions":
        return _run_sessions(args)
    if args.command == "investigate":
        return _run_investigate(args)
    if args.command == "triage":
        return _run_triage(args)
    if args.command == "export":
        return _run_export(args)
    if args.command == "notify":
        return _run_notify(args)
    raise AssertionError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    sys.exit(main())