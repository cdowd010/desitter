"""Epistemic domain kernel.

Models research truth as a directed graph of typed nodes (claims, 
assumptions, predictions, analyses, …) and typed edges with
bidirectional invariants.

Dependency rule: zero external imports. Only stdlib. This layer must be
fast, portable, and free of supply-chain risk.

Public surface:
  from episteme.epistemic.types import ClaimId, Finding, Severity, …
  from episteme.epistemic.model import Claim, Assumption, Prediction, …
  from episteme.epistemic.graph import EpistemicGraph
  from episteme.epistemic.invariants import validate_all
  from episteme.epistemic.ports import GraphRepository, GraphRenderer, …
"""

from .model import (
    Analysis,
    Assumption,
    Claim,
    DeadEnd,
    Discovery,
    IndependenceGroup,
    Observation,
    PairwiseSeparation,
    Parameter,
    Prediction,
    Theory,
)
from .types import (
    AnalysisId,
    AssumptionId,
    AssumptionType,
    ClaimCategory,
    ClaimId,
    ClaimStatus,
    ClaimType,
    ConfidenceTier,
    Criticality,
    DeadEndId,
    DeadEndStatus,
    DiscoveryId,
    DiscoveryStatus,
    EvidenceKind,
    Finding,
    IndependenceGroupId,
    MeasurementRegime,
    ObservationId,
    ObservationStatus,
    ParameterId,
    PairwiseSeparationId,
    PredictionId,
    PredictionStatus,
    Severity,
    TheoryId,
    TheoryStatus,
)
from .errors import (
    BrokenReferenceError,
    CycleError,
    DuplicateIdError,
    EpistemicError,
    InvariantViolation,
)
from .graph import EpistemicGraph

__all__ = [
    # types
    "ClaimId", "AssumptionId", "PredictionId", "TheoryId", "DiscoveryId",
    "AnalysisId", "IndependenceGroupId", "ParameterId", "DeadEndId",
    "PairwiseSeparationId", "ObservationId",
    "Severity", "Finding", "ConfidenceTier", "EvidenceKind", "MeasurementRegime",
    "PredictionStatus", "DeadEndStatus", "ClaimStatus", "TheoryStatus", "DiscoveryStatus",
    "ObservationStatus", "Criticality",
    "AssumptionType", "ClaimType", "ClaimCategory",
    # model
    "Claim", "Assumption", "Prediction", "Theory", "IndependenceGroup",
    "PairwiseSeparation", "Analysis", "Discovery", "DeadEnd", "Parameter",
    "Observation",
    # graph
    "EpistemicGraph", "EpistemicError", "DuplicateIdError", "BrokenReferenceError",
    "CycleError", "InvariantViolation",
]
