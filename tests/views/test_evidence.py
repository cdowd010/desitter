"""Tests for the evidence summary view."""
from __future__ import annotations

from datetime import date

import pytest

from episteme.epistemic.graph import EpistemicGraph
from episteme.epistemic.model import (
    Analysis,
    AnalysisId,
    Assumption,
    AssumptionId,
    AssumptionType,
    Hypothesis,
    HypothesisId,
    HypothesisType,
    Observation,
    ObservationId,
    ObservationStatus,
    Parameter,
    ParameterId,
    Prediction,
    PredictionId,
    PredictionStatus,
    Theory,
    TheoryId,
    TheoryStatus,
)
from episteme.epistemic.types import (
    ConfidenceTier,
    Criticality,
    EvidenceKind,
    HypothesisStatus,
    MeasurementRegime,
)
from episteme.views.evidence import evidence_summary


def test_evidence_summary_basic(base_graph):
    """Evidence summary for C-001 includes its prediction, assumption, and theory."""
    summary = evidence_summary(base_graph, HypothesisId("C-001"))

    assert summary.hypothesis_id == HypothesisId("C-001")
    assert summary.hypothesis_statement == "Catalyst X increases yield"
    assert summary.hypothesis_status == HypothesisStatus.ACTIVE

    # P-001 is the only prediction depending on C-001
    assert len(summary.predictions) == 1
    pred = summary.predictions[0]
    assert pred.id == PredictionId("P-001")
    assert pred.status == PredictionStatus.PENDING
    assert pred.tier == ConfidenceTier.FULLY_SPECIFIED
    assert pred.predicted == 0.15

    # P-001 has one observation (OBS-002)
    assert len(pred.observations) == 1
    assert pred.observations[0].id == ObservationId("OBS-002")
    assert pred.observations[0].status == ObservationStatus.VALIDATED

    # A-001 is the only assumption for C-001 (direct)
    assert len(summary.assumptions) == 1
    a = summary.assumptions[0]
    assert a.id == AssumptionId("A-001")
    assert a.criticality == Criticality.LOAD_BEARING
    assert a.direct is True

    # T-001 is the motivating theory
    assert len(summary.theories) == 1
    assert summary.theories[0].id == TheoryId("T-001")
    assert summary.theories[0].title == "Catalysis Theory"

    # Status counts
    assert summary.pending_count == 1
    assert summary.confirmed_count == 0
    assert summary.refuted_count == 0
    assert summary.stressed_count == 0


def test_evidence_summary_missing_hypothesis(base_graph):
    """Requesting a summary for a non-existent hypothesis raises KeyError."""
    with pytest.raises(KeyError):
        evidence_summary(base_graph, HypothesisId("C-MISSING"))


def test_evidence_summary_with_stale_analysis(base_graph):
    """An analysis linked to the hypothesis should be flagged stale when params are outdated."""
    # Link AN-001 to C-001 by updating the hypothesis to include it
    h = base_graph.get_hypothesis(HypothesisId("C-001"))
    updated = Hypothesis(
        id=h.id,
        statement=h.statement,
        type=h.type,
        scope=h.scope,
        refutation_criteria=h.refutation_criteria,
        status=h.status,
        category=h.category,
        assumptions=h.assumptions,
        depends_on=h.depends_on,
        analyses={AnalysisId("AN-001")},
        theories=h.theories,
    )
    graph = base_graph.update_hypothesis(updated)

    summary = evidence_summary(graph, HypothesisId("C-001"))

    assert len(summary.analyses) == 1
    assert summary.analyses[0].id == AnalysisId("AN-001")
    assert summary.analyses[0].has_result is True
    assert summary.analyses[0].stale is True


def test_evidence_summary_status_counts():
    """Status counters reflect the predictions correctly."""
    graph = EpistemicGraph()
    graph = graph.register_assumption(
        Assumption(
            id=AssumptionId("A-1"),
            statement="some assumption",
            type=AssumptionType.EMPIRICAL,
            scope="global",
        )
    )
    graph = graph.register_hypothesis(
        Hypothesis(
            id=HypothesisId("H-1"),
            statement="test",
            type=HypothesisType.FOUNDATIONAL,
            scope="global",
            refutation_criteria="show it fails",
            assumptions={AssumptionId("A-1")},
        )
    )
    graph = graph.register_prediction(
        Prediction(
            id=PredictionId("P-1"),
            observable="x",
            tier=ConfidenceTier.FULLY_SPECIFIED,
            status=PredictionStatus.CONFIRMED,
            evidence_kind=EvidenceKind.NOVEL_PREDICTION,
            measurement_regime=MeasurementRegime.MEASURED,
            predicted=1.0,
            hypothesis_ids={HypothesisId("H-1")},
        )
    )
    graph = graph.register_prediction(
        Prediction(
            id=PredictionId("P-2"),
            observable="y",
            tier=ConfidenceTier.CONDITIONAL,
            status=PredictionStatus.REFUTED,
            evidence_kind=EvidenceKind.RETRODICTION,
            measurement_regime=MeasurementRegime.MEASURED,
            predicted=2.0,
            hypothesis_ids={HypothesisId("H-1")},
        )
    )
    graph = graph.register_prediction(
        Prediction(
            id=PredictionId("P-3"),
            observable="z",
            tier=ConfidenceTier.FULLY_SPECIFIED,
            status=PredictionStatus.STRESSED,
            evidence_kind=EvidenceKind.NOVEL_PREDICTION,
            measurement_regime=MeasurementRegime.MEASURED,
            predicted=3.0,
            hypothesis_ids={HypothesisId("H-1")},
        )
    )

    summary = evidence_summary(graph, HypothesisId("H-1"))

    assert summary.confirmed_count == 1
    assert summary.refuted_count == 1
    assert summary.stressed_count == 1
    assert summary.pending_count == 0
    assert len(summary.predictions) == 3


def test_evidence_summary_transitive_assumptions():
    """Transitive assumptions are included and marked as indirect."""
    graph = EpistemicGraph()
    graph = graph.register_assumption(
        Assumption(
            id=AssumptionId("A-base"),
            statement="base assumption",
            type=AssumptionType.EMPIRICAL,
            scope="global",
            criticality=Criticality.HIGH,
        )
    )
    graph = graph.register_assumption(
        Assumption(
            id=AssumptionId("A-derived"),
            statement="derived assumption",
            type=AssumptionType.EMPIRICAL,
            scope="global",
            depends_on={AssumptionId("A-base")},
        )
    )
    graph = graph.register_hypothesis(
        Hypothesis(
            id=HypothesisId("H-1"),
            statement="test",
            type=HypothesisType.FOUNDATIONAL,
            scope="global",
            refutation_criteria="show it fails",
            assumptions={AssumptionId("A-derived")},
        )
    )

    summary = evidence_summary(graph, HypothesisId("H-1"))

    assert len(summary.assumptions) == 2
    by_id = {a.id: a for a in summary.assumptions}
    assert by_id[AssumptionId("A-derived")].direct is True
    assert by_id[AssumptionId("A-base")].direct is False
    assert by_id[AssumptionId("A-base")].criticality == Criticality.HIGH
