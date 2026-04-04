"""Value types and type aliases for the epistemic domain.

No external dependencies. No I/O. Pure data definitions.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import NewType


# ── Typed identifiers ─────────────────────────────────────────────
# NewType gives nominal typing: ClaimId and AnalysisId are both str at
# runtime, but the type checker treats them as distinct types.

ClaimId = NewType("ClaimId", str)
AssumptionId = NewType("AssumptionId", str)
PredictionId = NewType("PredictionId", str)
TheoryId = NewType("TheoryId", str)
DiscoveryId = NewType("DiscoveryId", str)
AnalysisId = NewType("AnalysisId", str)
IndependenceGroupId = NewType("IndependenceGroupId", str)
ParameterId = NewType("ParameterId", str)
ConceptId = NewType("ConceptId", str)
DeadEndId = NewType("DeadEndId", str)
PairwiseSeparationId = NewType("PairwiseSeparationId", str)



# ── Severity ──────────────────────────────────────────────────────

class Severity(Enum):
    INFO = auto()
    WARNING = auto()
    CRITICAL = auto()


@dataclass
class Finding:
    """One validation result."""
    severity: Severity
    source: str
    message: str


# ── Confidence tiers ──────────────────────────────────────────────

class ConfidenceTier(Enum):
    """How strongly a prediction is constrained.

    A: Zero free parameters — pure prediction from theory.
    B: Conditional on stated assumptions beyond the core theory.
    C: Fit/consistency check — not a novel prediction.
    """
    A = "A"
    B = "B"
    C = "C"


# ── Evidence classification ───────────────────────────────────────

class EvidenceKind(Enum):
    NOVEL_PREDICTION = "novel_prediction"
    RETRODICTION = "retrodiction"
    FIT_CONSISTENCY = "fit_consistency"


class MeasurementRegime(Enum):
    MEASURED = "measured"
    BOUND_ONLY = "bound_only"
    UNMEASURED = "unmeasured"


class PredictionStatus(Enum):
    CONFIRMED = "CONFIRMED"
    STRESSED = "STRESSED"
    REFUTED = "REFUTED"
    PENDING = "PENDING"
    NOT_YET_TESTABLE = "NOT_YET_TESTABLE"


class DeadEndStatus(Enum):
    ACTIVE = "active"
    RESOLVED = "resolved"
    ARCHIVED = "archived"
