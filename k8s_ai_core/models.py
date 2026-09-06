"""Stable JSON-serializable models for investigation results."""

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List


@dataclass(frozen=True)
class Evidence:
    """A directly observed fact from an evidence source."""

    fact: str
    source: str
    resource: str = ""


@dataclass(frozen=True)
class Hypothesis:
    """A cause ranked from observed evidence, not from model speculation."""

    title: str
    confidence: str
    rationale: str
    evidence: List[Evidence] = field(default_factory=list)


@dataclass(frozen=True)
class Recommendation:
    """A non-executed next step with an explicit safety boundary."""

    action: str
    reason: str
    risk: str
    verification: str
    requires_approval: bool = True


@dataclass
class InvestigationReport:
    """Portable report contract shared by CLI, future UI, and AI adapters."""

    question: str
    bundle: str
    status: str
    hypotheses: List[Hypothesis] = field(default_factory=list)
    evidence: List[Evidence] = field(default_factory=list)
    recommendations: List[Recommendation] = field(default_factory=list)
    unknowns: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
