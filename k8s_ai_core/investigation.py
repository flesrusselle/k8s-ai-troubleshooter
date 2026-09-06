"""Deterministic investigation over redacted evidence bundles."""

import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from .models import Evidence, Hypothesis, InvestigationReport, Recommendation, ResourceSpike

# Default threshold (%) above which a container is considered spiking.
# Override via the spike_threshold parameter on investigate_bundle().
DEFAULT_SPIKE_THRESHOLD = 80

SIGNALS: Tuple[Tuple[str, str], ...] = (
    ("OOMKilled", "OOMKilled"),
    ("CrashLoopBackOff", "CrashLoopBackOff"),
    ("ImagePullBackOff", "ImagePullBackOff"),
    ("ErrImagePull", "ErrImagePull"),
    ("FailedScheduling", "FailedScheduling"),
    ("Pending", "Pending"),
    ("Readiness probe failure", "Readiness probe failed"),
    ("Liveness probe failure", "Liveness probe failed"),
)


RECOMMENDATIONS: Dict[str, Recommendation] = {
    "OOMKilled": Recommendation(
        action="Inspect the workload memory profile and compare its configured limit with observed usage.",
        reason="The container termination reason indicates it exceeded its memory limit.",
        risk="Changing memory requests or limits can affect scheduling and node capacity.",
        verification="Check the next container lifecycle and memory usage after an approved change.",
    ),
    "CrashLoopBackOff": Recommendation(
        action="Inspect current and previous container logs, events, probes, and the owning workload revision.",
        reason="Repeated container startup failure is present, but the exit cause requires confirmation.",
        risk="Restarting or changing a workload can destroy diagnostic state or affect availability.",
        verification="Confirm the pod becomes Ready and restart counts stop increasing.",
    ),
    "ImagePullBackOff": Recommendation(
        action="Verify the image reference, registry reachability, and image pull credentials without exposing credential values.",
        reason="The kubelet cannot obtain the configured image.",
        risk="Changing an image or pull credential affects the deployed workload.",
        verification="Confirm the new pod pulls the image and reaches Ready.",
    ),
    "ErrImagePull": Recommendation(
        action="Inspect the image name, tag or digest, registry events, and pull-secret references.",
        reason="The image pull operation returned an error.",
        risk="Changing image configuration affects which artifact is executed.",
        verification="Confirm the image pull succeeds and verify the deployed digest.",
    ),
    "FailedScheduling": Recommendation(
        action="Review scheduler events, resource requests, node conditions, taints, tolerations, and affinity.",
        reason="The scheduler reported that the pod could not be placed.",
        risk="Changing requests, tolerations, or placement rules can move workloads across nodes.",
        verification="Confirm the pod is scheduled on an appropriate node and remains healthy.",
    ),
    "Pending": Recommendation(
        action="Inspect pod conditions and recent scheduling, volume, and admission events.",
        reason="The pod has not reached a running state.",
        risk="Changing scheduling or storage settings can affect availability and capacity.",
        verification="Confirm the pod transitions to Running and Ready.",
    ),
    "Readiness probe failure": Recommendation(
        action="Compare the readiness probe path, port, timing, and service endpoints with the application behavior.",
        reason="The readiness probe is preventing the container from receiving traffic.",
        risk="Changing probes can route traffic to an unhealthy application.",
        verification="Confirm readiness succeeds and endpoints contain the intended pod.",
    ),
    "Liveness probe failure": Recommendation(
        action="Inspect liveness probe configuration and application startup or dependency timing.",
        reason="The liveness probe may be causing repeated container restarts.",
        risk="Relaxing liveness checks can leave a stuck process running.",
        verification="Confirm the container remains healthy without unnecessary restarts.",
    ),
}


def _files(bundle: Path) -> Iterable[Path]:
    return (path for path in bundle.rglob("*") if path.is_file() and path.name != "README.md")


def _read_evidence(bundle: Path) -> List[Tuple[Path, str]]:
    evidence = []
    for path in _files(bundle):
        try:
            evidence.append((path, path.read_text(encoding="utf-8", errors="replace")))
        except OSError:
            continue
    return evidence


# ── Resource unit conversion helpers ──────────────────────────────────────────

def _parse_cpu_millicores(value: str) -> Optional[float]:
    """Convert a kubectl top CPU string (e.g. '450m', '2') to millicores."""
    value = value.strip()
    if value.endswith("m"):
        try:
            return float(value[:-1])
        except ValueError:
            return None
    try:
        return float(value) * 1000
    except ValueError:
        return None


def _parse_memory_bytes(value: str) -> Optional[float]:
    """Convert a kubectl top memory string to bytes."""
    value = value.strip()
    units = {
        "Ki": 1024, "Mi": 1024 ** 2, "Gi": 1024 ** 3,
        "K":  1000, "M":  1000 ** 2, "G":  1000 ** 3,
    }
    for suffix, multiplier in units.items():
        if value.endswith(suffix):
            try:
                return float(value[: -len(suffix)]) * multiplier
            except ValueError:
                return None
    try:
        return float(value)  # plain bytes
    except ValueError:
        return None


def _pct(used: Optional[float], limit: Optional[float]) -> Optional[int]:
    """Return integer percentage, or None if either value is missing / zero."""
    if used is None or limit is None or limit == 0:
        return None
    return min(round(used / limit * 100), 100)


# ── Spike detection ───────────────────────────────────────────────────────────

# Pattern for a kubectl top pods --containers line:
#   NAMESPACE  POD  CONTAINER  CPU(cores)  MEMORY(bytes)
_TOP_LINE_RE = re.compile(
    r"^(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s*$"
)

# Pattern for a kubectl describe pod resource limits line:
#   <whitespace>cpu: 500m   or   memory: 2Gi
_LIMIT_RE = re.compile(r"^\s+(?:cpu|memory):\s+(\S+)", re.IGNORECASE)


def detect_spikes(
    bundle: Path,
    threshold: int = DEFAULT_SPIKE_THRESHOLD,
) -> List[ResourceSpike]:
    """Parse kubectl top output files in the bundle and return containers that
    exceed *threshold* percent of their configured resource limit.

    Spike detection is **best-effort**: if limits cannot be parsed from the
    describe output, the container is skipped rather than guessed.
    """
    spikes: List[ResourceSpike] = []

    # Collect all top-pods-containers files.  The collector writes them with
    # names containing "top" (e.g. "top-pods.txt", "top-pods-containers.txt").
    top_files = [
        p for p in _files(bundle)
        if "top" in p.name.lower() and p.suffix in (".txt", "")
    ]
    if not top_files:
        return spikes

    # Build a coarse limits map: (namespace, pod, container) -> {cpu_m, mem_b}
    # by scanning describe files.  This is approximate — describe output can
    # list Limits under a Containers block.  We extract the first cpu/memory
    # limit values following a "Limits:" heading.
    limits_map: Dict[Tuple[str, str, str], Dict[str, float]] = {}
    describe_files = [
        p for p in _files(bundle)
        if "describe" in p.name.lower() and p.suffix in (".txt", "")
    ]
    for dp in describe_files:
        try:
            text = dp.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        # Quick scan: find pod name, then Limits block
        current_pod = None
        current_ns = None
        in_limits = False
        cpu_limit: Optional[float] = None
        mem_limit: Optional[float] = None
        for line in text.splitlines():
            # Detect pod/namespace header lines from kubectl describe pods output
            if line.startswith("Name:"):
                current_pod = line.split(":", 1)[1].strip()
                in_limits = False
                cpu_limit = None
                mem_limit = None
            elif line.startswith("Namespace:"):
                current_ns = line.split(":", 1)[1].strip()
            elif "Limits:" in line:
                in_limits = True
            elif in_limits and ("Requests:" in line or "Environment:" in line or "Mounts:" in line):
                in_limits = False
            elif in_limits and current_pod and current_ns:
                m = _LIMIT_RE.match(line)
                if m:
                    val = m.group(1)
                    if "cpu" in line.lower():
                        cpu_limit = _parse_cpu_millicores(val)
                    elif "memory" in line.lower():
                        mem_limit = _parse_memory_bytes(val)
                    if cpu_limit is not None and mem_limit is not None:
                        key = (current_ns, current_pod, "<all>")
                        limits_map[key] = {"cpu_m": cpu_limit, "mem_b": mem_limit}

    for tp in top_files:
        try:
            lines = tp.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for line in lines:
            m = _TOP_LINE_RE.match(line)
            if not m:
                continue
            ns, pod, container, cpu_raw, mem_raw = m.groups()
            if ns.upper() in ("NAMESPACE", "NAME"):  # header row
                continue

            # Look up limits: prefer exact container key, fall back to pod-level.
            lim = limits_map.get((ns, pod, container)) or limits_map.get((ns, pod, "<all>"))

            cpu_used = _parse_cpu_millicores(cpu_raw)
            mem_used = _parse_memory_bytes(mem_raw)

            # CPU spike
            cpu_pct = _pct(cpu_used, lim.get("cpu_m") if lim else None)
            if cpu_pct is not None and cpu_pct >= threshold:
                severity = "HIGH" if cpu_pct >= 90 else "MEDIUM"
                spikes.append(ResourceSpike(
                    namespace=ns, pod=pod, container=container,
                    resource="cpu",
                    usage_raw=cpu_raw,
                    limit_raw=f"{round(lim['cpu_m'])}m" if lim else "unknown",
                    usage_pct=cpu_pct,
                    severity=severity,
                ))

            # Memory spike
            mem_pct = _pct(mem_used, lim.get("mem_b") if lim else None)
            if mem_pct is not None and mem_pct >= threshold:
                severity = "HIGH" if mem_pct >= 90 else "MEDIUM"
                spikes.append(ResourceSpike(
                    namespace=ns, pod=pod, container=container,
                    resource="memory",
                    usage_raw=mem_raw,
                    limit_raw=f"{round((lim['mem_b']) / 1024 / 1024)}Mi" if lim else "unknown",
                    usage_pct=mem_pct,
                    severity=severity,
                ))
    return spikes


def investigate_bundle(
    bundle_path: str,
    question: str = "Investigate the evidence bundle",
    spike_threshold: int = DEFAULT_SPIKE_THRESHOLD,
) -> InvestigationReport:
    """Return a conservative report based only on text present in a bundle."""
    bundle = Path(bundle_path)
    if not bundle.is_dir():
        return InvestigationReport(
            question=question,
            bundle=str(bundle),
            status="UNAVAILABLE",
            unknowns=[f"Evidence bundle does not exist: {bundle}"],
        )

    observations = _read_evidence(bundle)
    spikes = detect_spikes(bundle, threshold=spike_threshold)
    facts: List[Evidence] = []
    hypotheses: List[Hypothesis] = []
    recommendations: List[Recommendation] = []
    seen = set()

    for signal, marker in SIGNALS:
        matches = [(path, text) for path, text in observations if marker.lower() in text.lower()]
        if not matches or signal in seen:
            continue
        seen.add(signal)
        signal_evidence = [
            Evidence(
                fact=f"Evidence contains {signal}.",
                source=str(path.relative_to(bundle)),
            )
            for path, _ in matches[:5]
        ]
        facts.extend(signal_evidence)
        confidence = "HIGH" if signal in {"OOMKilled", "FailedScheduling", "ImagePullBackOff", "ErrImagePull"} else "MEDIUM"
        rationale = {
            "OOMKilled": "The recorded termination reason directly identifies an out-of-memory kill.",
            "CrashLoopBackOff": "The pod is repeatedly failing to start; the underlying exit cause still needs confirmation.",
            "ImagePullBackOff": "The kubelet is repeatedly unable to pull the configured image.",
            "ErrImagePull": "The evidence records an image pull error.",
            "FailedScheduling": "The scheduler reported a placement failure.",
            "Pending": "The pod has not reached a running state; the blocking condition is not yet proven.",
            "Readiness probe failure": "Readiness is failing, so traffic eligibility is affected.",
            "Liveness probe failure": "Liveness is failing and may explain repeated restarts.",
        }[signal]
        hypotheses.append(Hypothesis(signal, confidence, rationale, signal_evidence))
        recommendations.append(RECOMMENDATIONS[signal])

    if not hypotheses:
        return InvestigationReport(
            question=question,
            bundle=str(bundle),
            status="NO_SIGNAL",
            unknowns=["No supported failure signal was found in the evidence bundle."],
        )

    unknowns = [
        "This report uses text evidence only; resource relationships and timestamps are not yet normalized.",
        "No remediation was executed or verified.",
    ]
    # Elevate status when spikes are present alongside hypotheses.
    has_high_spike = any(s.severity == "HIGH" for s in spikes)
    if has_high_spike:
        status = "CRITICAL"
    elif any(h.confidence == "MEDIUM" for h in hypotheses):
        status = "DEGRADED"
    else:
        status = "ATTENTION"
    return InvestigationReport(
        question=question,
        bundle=str(bundle),
        status=status,
        hypotheses=hypotheses,
        evidence=facts,
        recommendations=recommendations,
        unknowns=unknowns,
        resource_spikes=spikes,
    )
