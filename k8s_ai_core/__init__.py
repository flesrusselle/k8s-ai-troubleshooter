"""Shared investigation models and deterministic analysis."""

from .investigation import investigate_bundle
from .models import InvestigationReport

__all__ = ["InvestigationReport", "investigate_bundle"]
