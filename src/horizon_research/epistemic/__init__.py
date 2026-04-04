"""Epistemic domain kernel.

The gravity well of the system. Models research truth as a directed graph
of typed nodes (claims, assumptions, predictions, scripts, …) and typed
edges with bidirectional invariants.

Dependency rule: zero external imports. Only stdlib. This layer must be
fast, portable, and free of supply-chain risk.

Public surface:
  from horizon_research.epistemic.types import ClaimId, Finding, Severity, …
  from horizon_research.epistemic.model import Claim, Assumption, Prediction, …
  from horizon_research.epistemic.web import EpistemicWeb
  from horizon_research.epistemic.invariants import validate_all
  from horizon_research.epistemic.ports import WebRepository, WebRenderer, …
"""

from .model import (
    Analysis,
    Assumption,
    Claim,
    Concept,
    DeadEnd,
    Discovery,
    IndependenceGroup,
    PairwiseSeparation,
    Parameter,
    Prediction,
    Theory,
)
from .types import (
    AnalysisId,
    AssumptionId,
    ClaimId,
    ConceptId,
    ConfidenceTier,
    DeadEndId,
    DeadEndStatus,
    DiscoveryId,
    EvidenceKind,
    Finding,
    IndependenceGroupId,
    MeasurementRegime,
    ParameterId,
    PairwiseSeparationId,
    PredictionId,
    PredictionStatus,
    Severity,
    TheoryId,
)
from .web import (
    BrokenReferenceError,
    CycleError,
    DuplicateIdError,
    EpistemicError,
    EpistemicWeb,
    InvariantViolation,
)

__all__ = [
    # types
    "ClaimId", "AssumptionId", "PredictionId", "TheoryId", "DiscoveryId",
    "AnalysisId", "IndependenceGroupId", "ParameterId", "ConceptId", "DeadEndId",
    "PairwiseSeparationId",
    "Severity", "Finding", "ConfidenceTier", "EvidenceKind", "MeasurementRegime",
    "PredictionStatus", "DeadEndStatus",
    # model
    "Claim", "Assumption", "Prediction", "Theory", "IndependenceGroup",
    "PairwiseSeparation", "Analysis", "Discovery", "DeadEnd", "Concept", "Parameter",
    # web
    "EpistemicWeb", "EpistemicError", "DuplicateIdError", "BrokenReferenceError",
    "CycleError", "InvariantViolation",
]
