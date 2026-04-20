"""Tests for on-demand semantic invariant validators."""
from __future__ import annotations

from episteme.epistemic.model import (
    Hypothesis,
    HypothesisId,
    HypothesisStatus,
    HypothesisType,
    Objective,
    ObjectiveId,
    ObjectiveKind,
    ObjectiveStatus,
    Prediction,
    PredictionId,
    PredictionStatus,
)
from episteme.epistemic.invariants import validate_all, validate_supersession_chains
from episteme.epistemic.types import Severity


def test_objective_abandonment_impact(base_graph):
    """Claims whose only motivating objective is ABANDONED should trigger a warning."""
    graph = base_graph.transition_objective(ObjectiveId("T-001"), ObjectiveStatus.ABANDONED)
    findings = validate_all(graph)
    assert any("theoretical motivation" in f.message for f in findings)


def test_load_bearing_assumption_untested(base_graph):
    """LOAD_BEARING assumptions with no tested_by links should trigger a critical finding."""
    findings = validate_all(base_graph)
    assert any("LOAD_BEARING" in f.message for f in findings)


# ── Supersession chain validators ──────────────────────────────────


def test_retracted_hypothesis_missing_superseded_by(base_graph):
    """A RETRACTED hypothesis without superseded_by triggers a WARNING."""
    graph = base_graph.transition_hypothesis(
        HypothesisId("C-001"), HypothesisStatus.RETRACTED
    )
    findings = validate_supersession_chains(graph)
    warnings = [f for f in findings if f.severity == Severity.WARNING]
    assert any("provenance chain" in f.message and "C-001" in f.source for f in warnings)


def test_hypothesis_superseded_by_dangling_ref(base_graph):
    """superseded_by pointing to a non-existent hypothesis triggers CRITICAL."""
    graph = base_graph.update_hypothesis(
        Hypothesis(
            id=HypothesisId("C-001"),
            statement="Catalyst X increases yield",
            type=HypothesisType.FOUNDATIONAL,
            scope="global",
            status=HypothesisStatus.REVISED,
            superseded_by=HypothesisId("C-999"),
        )
    )
    findings = validate_supersession_chains(graph)
    criticals = [f for f in findings if f.severity == Severity.CRITICAL]
    assert any("C-999" in f.message for f in criticals)


def test_superseded_objective_missing_superseded_by(base_graph):
    """A SUPERSEDED objective without superseded_by triggers a WARNING."""
    graph = base_graph.transition_objective(
        ObjectiveId("T-001"), ObjectiveStatus.SUPERSEDED
    )
    findings = validate_supersession_chains(graph)
    warnings = [f for f in findings if f.severity == Severity.WARNING]
    assert any("T-001" in f.source for f in warnings)


def test_prediction_supersedes_dangling_ref(base_graph):
    """supersedes pointing to a non-existent prediction triggers CRITICAL."""
    graph = base_graph.register_prediction(
        Prediction(
            id=PredictionId("P-002"),
            observable="yield",
            predicted=0.20,
            status=PredictionStatus.PENDING,
            supersedes=PredictionId("P-999"),
        )
    )
    findings = validate_supersession_chains(graph)
    criticals = [f for f in findings if f.severity == Severity.CRITICAL]
    assert any("P-999" in f.message for f in criticals)


def test_valid_supersession_chain_no_findings(base_graph):
    """A valid supersession chain produces no supersession findings."""
    # Register a successor hypothesis and link the old one
    graph = base_graph.register_hypothesis(
        Hypothesis(
            id=HypothesisId("C-002"),
            statement="Catalyst X increases yield v2",
        )
    )
    graph = graph.update_hypothesis(
        Hypothesis(
            id=HypothesisId("C-001"),
            statement="Catalyst X increases yield",
            type=HypothesisType.FOUNDATIONAL,
            scope="global",
            status=HypothesisStatus.REVISED,
            superseded_by=HypothesisId("C-002"),
        )
    )
    findings = validate_supersession_chains(graph)
    assert not findings
