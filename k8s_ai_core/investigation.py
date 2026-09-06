"""Deterministic investigation over redacted evidence bundles."""

from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from .models import Evidence, Hypothesis, InvestigationReport, Recommendation

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


def investigate_bundle(bundle_path: str, question: str = "Investigate the evidence bundle") -> InvestigationReport:
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
    return InvestigationReport(
        question=question,
        bundle=str(bundle),
        status="DEGRADED" if any(h.confidence == "MEDIUM" for h in hypotheses) else "ATTENTION",
        hypotheses=hypotheses,
        evidence=facts,
        recommendations=recommendations,
        unknowns=unknowns,
    )
