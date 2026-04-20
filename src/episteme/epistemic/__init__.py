"""Epistemic domain kernel.

Models research truth as a directed graph of typed nodes (hypotheses, 
assumptions, predictions, analyses, …) and typed edges with
bidirectional invariants.

Dependency rule: zero external imports. Only stdlib. This layer must be
fast, portable, and free of supply-chain risk.

Public surface:
  from episteme.epistemic.types import HypothesisId, Finding, Severity, …
  from episteme.epistemic.model import Hypothesis, Assumption, Prediction, …
  from episteme.epistemic.graph import EpistemicGraph
  from episteme.epistemic.invariants import validate_all
  from episteme.epistemic.ports import GraphRepository, GraphRenderer, …
"""

from .model import (
    Analysis,
    Assumption,
    Hypothesis,
    DeadEnd,
    Discovery,
    IndependenceGroup,
    Observation,
    PairwiseSeparation,
    Parameter,
    Prediction,
    Objective,
)
from .types import (
    AnalysisId,
    AssumptionId,
    AssumptionStatus,
    AssumptionType,
    HypothesisCategory,
    HypothesisId,
    HypothesisStatus,
    HypothesisType,
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
    ObjectiveId,
    ObjectiveKind,
    ObjectiveStatus,
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
    "HypothesisId", "AssumptionId", "PredictionId", "ObjectiveId", "DiscoveryId",
    "AnalysisId", "IndependenceGroupId", "ParameterId", "DeadEndId",
    "PairwiseSeparationId", "ObservationId",
    "Severity", "Finding", "ConfidenceTier", "EvidenceKind", "MeasurementRegime",
    "PredictionStatus", "DeadEndStatus", "HypothesisStatus", "ObjectiveStatus", "ObjectiveKind", "DiscoveryStatus",
    "ObservationStatus", "Criticality", "AssumptionStatus",
    "AssumptionType", "HypothesisType", "HypothesisCategory",
    # model
    "Hypothesis", "Assumption", "Prediction", "Objective", "IndependenceGroup",
    "PairwiseSeparation", "Analysis", "Discovery", "DeadEnd", "Parameter",
    "Observation",
    # graph
    "EpistemicGraph", "EpistemicError", "DuplicateIdError", "BrokenReferenceError",
    "CycleError", "InvariantViolation",
]
