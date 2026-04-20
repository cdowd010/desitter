"""Tests for EpistemicGraph mutation operations."""
from __future__ import annotations

import pytest

from episteme.epistemic.errors import InvariantViolation
from episteme.epistemic.model import (
    Assumption,
    AssumptionId,
    AssumptionType,
    HypothesisId,
    HypothesisStatus,
    ObservationId,
    Prediction,
    PredictionId,
    PredictionStatus,
    ObjectiveId,
    ObjectiveStatus,
)
from episteme.epistemic.types import (
    AssumptionStatus,
    ConfidenceTier,
    Criticality,
    DeadEndStatus,
    DiscoveryStatus,
    EvidenceKind,
    MeasurementRegime,
    ObservationStatus,
)


def test_objective_hypothesis_bidirectional_links(base_graph):
    """Registering a Hypothesis with objectives= auto-populates Objective.motivates_hypotheses."""
    assert HypothesisId("C-001") in base_graph.objectives[ObjectiveId("T-001")].motivates_hypotheses
    assert ObjectiveId("T-001") in base_graph.hypotheses[HypothesisId("C-001")].objectives


def test_prediction_stress_criteria_stored(base_graph):
    """stress_criteria field is persisted on the Prediction."""
    p = base_graph.predictions[PredictionId("P-001")]
    assert p.stress_criteria == "Yield increase <10% but >5% would be stressed"


def test_standalone_observation(base_graph):
    """Observations can exist without linking to any prediction."""
    obs = base_graph.observations[ObservationId("OBS-001")]
    assert obs.predictions == set()


def test_observation_prediction_bidirectional(base_graph):
    """Registering an observation with predictions= auto-populates Prediction.observations."""
    assert ObservationId("OBS-002") in base_graph.predictions[PredictionId("P-001")].observations


def test_objective_removal_scrubs_hypothesis_objectives(base_graph):
    """Removing a Objective clears its id from all Hypothesis.objectives sets."""
    graph = base_graph.remove_prediction(PredictionId("P-001"))
    graph = graph.remove_hypothesis(HypothesisId("C-001"))
    graph = graph.remove_objective(ObjectiveId("T-001"))
    assert ObjectiveId("T-001") not in graph.objectives


def test_observation_removal_cleans_prediction_backlink(base_graph):
    """Removing an Observation tears down its Prediction.observations backlink."""
    graph = base_graph.remove_observation(ObservationId("OBS-002"))
    assert ObservationId("OBS-002") not in graph.predictions[PredictionId("P-001")].observations


# ── Tier 1 guards: register_prediction ────────────────────────────


def test_register_rejects_fully_specified_with_free_params(base_graph):
    """FULLY_SPECIFIED + free_params > 0 is logically impossible."""
    bad = Prediction(
        id=PredictionId("P-BAD"),
        observable="x",
        predicted=1.0,
        tier=ConfidenceTier.FULLY_SPECIFIED,
        free_params=2,
        hypothesis_ids={HypothesisId("C-001")},
    )
    with pytest.raises(InvariantViolation, match="FULLY_SPECIFIED"):
        base_graph.register_prediction(bad)


def test_register_rejects_tests_conditional_overlap(base_graph):
    """A prediction cannot both test and condition on the same assumption."""
    bad = Prediction(
        id=PredictionId("P-BAD"),
        observable="x",
        predicted=1.0,
        tier=ConfidenceTier.CONDITIONAL,
        hypothesis_ids={HypothesisId("C-001")},
        tests_assumptions={AssumptionId("A-001")},
        conditional_on={AssumptionId("A-001")},
    )
    with pytest.raises(InvariantViolation, match="both test and condition"):
        base_graph.register_prediction(bad)


def test_register_rejects_fit_check_with_novel_prediction(base_graph):
    """FIT_CHECK + NOVEL_PREDICTION is an invalid evidence pairing."""
    bad = Prediction(
        id=PredictionId("P-BAD"),
        observable="x",
        predicted=1.0,
        tier=ConfidenceTier.FIT_CHECK,
        evidence_kind=EvidenceKind.NOVEL_PREDICTION,
        hypothesis_ids={HypothesisId("C-001")},
    )
    with pytest.raises(InvariantViolation, match="FIT_CHECK"):
        base_graph.register_prediction(bad)


def test_register_rejects_fit_check_with_retrodiction(base_graph):
    """FIT_CHECK + RETRODICTION is an invalid evidence pairing."""
    bad = Prediction(
        id=PredictionId("P-BAD"),
        observable="x",
        predicted=1.0,
        tier=ConfidenceTier.FIT_CHECK,
        evidence_kind=EvidenceKind.RETRODICTION,
        hypothesis_ids={HypothesisId("C-001")},
    )
    with pytest.raises(InvariantViolation, match="FIT_CHECK"):
        base_graph.register_prediction(bad)


def test_register_allows_fit_check_with_fit_consistency(base_graph):
    """FIT_CHECK + FIT_CONSISTENCY is the valid pairing — should succeed."""
    ok = Prediction(
        id=PredictionId("P-FIT"),
        observable="x",
        predicted=1.0,
        tier=ConfidenceTier.FIT_CHECK,
        evidence_kind=EvidenceKind.FIT_CONSISTENCY,
        hypothesis_ids={HypothesisId("C-001")},
    )
    graph = base_graph.register_prediction(ok)
    assert PredictionId("P-FIT") in graph.predictions


# ── Tier 1 guards: update_prediction ──────────────────────────────


def test_update_rejects_fully_specified_with_free_params(base_graph):
    """update_prediction enforces the same consistency guards."""
    old = base_graph.predictions[PredictionId("P-001")]
    bad = Prediction(
        id=old.id,
        observable=old.observable,
        predicted=old.predicted,
        tier=ConfidenceTier.FULLY_SPECIFIED,
        free_params=3,
        hypothesis_ids=old.hypothesis_ids,
    )
    with pytest.raises(InvariantViolation, match="FULLY_SPECIFIED"):
        base_graph.update_prediction(bad)


# ── Tier 1 guards: transition_prediction ──────────────────────────


def test_transition_rejects_confirmed_without_observed_measured(base_graph):
    """MEASURED regime requires observed value before adjudication."""
    # P-001 is MEASURED with observed=None
    with pytest.raises(InvariantViolation, match="MEASURED"):
        base_graph.transition_prediction(
            PredictionId("P-001"), PredictionStatus.CONFIRMED
        )


def test_transition_rejects_stressed_without_observed_measured(base_graph):
    """MEASURED regime requires observed value before STRESSED too."""
    with pytest.raises(InvariantViolation, match="MEASURED"):
        base_graph.transition_prediction(
            PredictionId("P-001"), PredictionStatus.STRESSED
        )


def test_transition_rejects_refuted_without_observed_measured(base_graph):
    """MEASURED regime requires observed value before REFUTED too."""
    with pytest.raises(InvariantViolation, match="MEASURED"):
        base_graph.transition_prediction(
            PredictionId("P-001"), PredictionStatus.REFUTED
        )


def test_transition_rejects_confirmed_without_observed_bound(base_graph):
    """BOUND_ONLY regime requires observed_bound before adjudication."""
    bound_pred = Prediction(
        id=PredictionId("P-BOUND"),
        observable="upper limit",
        predicted=100.0,
        measurement_regime=MeasurementRegime.BOUND_ONLY,
        hypothesis_ids={HypothesisId("C-001")},
    )
    graph = base_graph.register_prediction(bound_pred)
    with pytest.raises(InvariantViolation, match="BOUND_ONLY"):
        graph.transition_prediction(
            PredictionId("P-BOUND"), PredictionStatus.CONFIRMED
        )


def test_transition_allows_confirmed_with_observed(base_graph):
    """MEASURED + observed present should allow adjudication."""
    observed_pred = Prediction(
        id=PredictionId("P-OBS"),
        observable="yield",
        predicted=0.15,
        observed=0.14,
        measurement_regime=MeasurementRegime.MEASURED,
        hypothesis_ids={HypothesisId("C-001")},
    )
    graph = base_graph.register_prediction(observed_pred)
    graph = graph.transition_prediction(
        PredictionId("P-OBS"), PredictionStatus.CONFIRMED
    )
    assert graph.predictions[PredictionId("P-OBS")].status == PredictionStatus.CONFIRMED


def test_transition_allows_pending_without_observed(base_graph):
    """Non-adjudicated transitions should not require observed values."""
    graph = base_graph.transition_prediction(
        PredictionId("P-001"), PredictionStatus.NOT_YET_TESTABLE
    )
    assert graph.predictions[PredictionId("P-001")].status == PredictionStatus.NOT_YET_TESTABLE


def test_transition_allows_unmeasured_adjudication(base_graph):
    """UNMEASURED regime does not require observed for adjudication."""
    unmeasured = Prediction(
        id=PredictionId("P-UNM"),
        observable="qualitative assessment",
        predicted="positive",
        measurement_regime=MeasurementRegime.UNMEASURED,
        hypothesis_ids={HypothesisId("C-001")},
    )
    graph = base_graph.register_prediction(unmeasured)
    graph = graph.transition_prediction(
        PredictionId("P-UNM"), PredictionStatus.CONFIRMED
    )
    assert graph.predictions[PredictionId("P-UNM")].status == PredictionStatus.CONFIRMED


# ── Transition guard tables ─────────────────────────────────────────


def test_prediction_superseded_is_terminal(base_graph):
    """SUPERSEDED predictions cannot be re-transitioned."""
    graph = base_graph.transition_prediction(
        PredictionId("P-001"), PredictionStatus.SUPERSEDED
    )
    with pytest.raises(InvariantViolation, match="Cannot transition"):
        graph.transition_prediction(
            PredictionId("P-001"), PredictionStatus.PENDING
        )


def test_hypothesis_retracted_is_terminal(base_graph):
    """RETRACTED hypotheses cannot be re-transitioned."""
    graph = base_graph.transition_hypothesis(
        HypothesisId("C-001"), HypothesisStatus.RETRACTED
    )
    with pytest.raises(InvariantViolation, match="Cannot transition"):
        graph.transition_hypothesis(
            HypothesisId("C-001"), HypothesisStatus.ACTIVE
        )


def test_hypothesis_deferred_can_resume(base_graph):
    """DEFERRED hypotheses can transition back to ACTIVE."""
    graph = base_graph.transition_hypothesis(
        HypothesisId("C-001"), HypothesisStatus.DEFERRED
    )
    graph = graph.transition_hypothesis(
        HypothesisId("C-001"), HypothesisStatus.ACTIVE
    )
    assert graph.hypotheses[HypothesisId("C-001")].status == HypothesisStatus.ACTIVE


def test_objective_achieved_is_terminal(base_graph):
    """ACHIEVED objectives cannot be re-transitioned."""
    graph = base_graph.transition_objective(
        ObjectiveId("T-001"), ObjectiveStatus.ACHIEVED
    )
    with pytest.raises(InvariantViolation, match="Cannot transition"):
        graph.transition_objective(
            ObjectiveId("T-001"), ObjectiveStatus.ACTIVE
        )


def test_refuted_can_retest(base_graph):
    """REFUTED predictions can transition back to PENDING for retesting."""
    observed_pred = Prediction(
        id=PredictionId("P-OBS2"),
        observable="yield",
        predicted=0.15,
        observed=999,
        measurement_regime=MeasurementRegime.MEASURED,
        hypothesis_ids={HypothesisId("C-001")},
    )
    graph = base_graph.register_prediction(observed_pred)
    graph = graph.transition_prediction(
        PredictionId("P-OBS2"), PredictionStatus.REFUTED
    )
    graph = graph.transition_prediction(
        PredictionId("P-OBS2"), PredictionStatus.PENDING
    )
    assert graph.predictions[PredictionId("P-OBS2")].status == PredictionStatus.PENDING


# ── Auto-supersession ─────────────────────────────────────────────


def test_register_with_supersedes_auto_transitions_predecessor(base_graph):
    """Registering P-002 with supersedes=P-001 auto-transitions P-001 to SUPERSEDED."""
    successor = Prediction(
        id=PredictionId("P-002"),
        observable="yield v2",
        predicted=0.20,
        supersedes=PredictionId("P-001"),
        hypothesis_ids={HypothesisId("C-001")},
    )
    graph = base_graph.register_prediction(successor)
    assert graph.predictions[PredictionId("P-001")].status == PredictionStatus.SUPERSEDED
    assert graph.predictions[PredictionId("P-002")].status == PredictionStatus.PENDING


def test_register_with_supersedes_validates_ref(base_graph):
    """supersedes pointing to nonexistent prediction raises BrokenReferenceError."""
    from episteme.epistemic.errors import BrokenReferenceError

    bad = Prediction(
        id=PredictionId("P-002"),
        observable="x",
        predicted=1.0,
        supersedes=PredictionId("P-NOPE"),
    )
    with pytest.raises(BrokenReferenceError, match="P-NOPE"):
        base_graph.register_prediction(bad)


def test_supersedes_already_superseded_is_noop(base_graph):
    """If predecessor is already SUPERSEDED, auto-transition doesn't fail."""
    graph = base_graph.transition_prediction(
        PredictionId("P-001"), PredictionStatus.SUPERSEDED
    )
    successor = Prediction(
        id=PredictionId("P-002"),
        observable="yield v2",
        predicted=0.20,
        supersedes=PredictionId("P-001"),
        hypothesis_ids={HypothesisId("C-001")},
    )
    graph = graph.register_prediction(successor)
    assert graph.predictions[PredictionId("P-001")].status == PredictionStatus.SUPERSEDED


# ── Assumption lifecycle ──────────────────────────────────────────


def test_assumption_default_status_is_active(base_graph):
    """Newly registered assumptions default to ACTIVE."""
    assert base_graph.assumptions[AssumptionId("A-001")].status == AssumptionStatus.ACTIVE


def test_transition_assumption_active_to_questioned(base_graph):
    """Assumptions can be questioned."""
    graph = base_graph.transition_assumption(
        AssumptionId("A-001"), AssumptionStatus.QUESTIONED
    )
    assert graph.assumptions[AssumptionId("A-001")].status == AssumptionStatus.QUESTIONED


def test_transition_assumption_questioned_to_falsified(base_graph):
    """Questioned assumptions can be falsified."""
    graph = base_graph.transition_assumption(
        AssumptionId("A-001"), AssumptionStatus.QUESTIONED
    )
    graph = graph.transition_assumption(
        AssumptionId("A-001"), AssumptionStatus.FALSIFIED
    )
    assert graph.assumptions[AssumptionId("A-001")].status == AssumptionStatus.FALSIFIED


def test_transition_assumption_falsified_is_terminal(base_graph):
    """FALSIFIED assumptions cannot be re-transitioned."""
    graph = base_graph.transition_assumption(
        AssumptionId("A-001"), AssumptionStatus.FALSIFIED
    )
    with pytest.raises(InvariantViolation, match="Cannot transition"):
        graph.transition_assumption(
            AssumptionId("A-001"), AssumptionStatus.ACTIVE
        )


def test_transition_assumption_questioned_can_resolve(base_graph):
    """A questioned assumption can return to ACTIVE if doubt is resolved."""
    graph = base_graph.transition_assumption(
        AssumptionId("A-001"), AssumptionStatus.QUESTIONED
    )
    graph = graph.transition_assumption(
        AssumptionId("A-001"), AssumptionStatus.ACTIVE
    )
    assert graph.assumptions[AssumptionId("A-001")].status == AssumptionStatus.ACTIVE


# ── Adjudication rationale ────────────────────────────────────────


def test_adjudication_rationale_stored(base_graph):
    """adjudication_rationale field is persisted on predictions."""
    pred = Prediction(
        id=PredictionId("P-ADJ"),
        observable="yield",
        predicted=0.15,
        observed=0.14,
        measurement_regime=MeasurementRegime.MEASURED,
        hypothesis_ids={HypothesisId("C-001")},
        adjudication_rationale="OBS-002 at 14.8 matches predicted 15.0 within 1-sigma",
    )
    graph = base_graph.register_prediction(pred)
    stored = graph.predictions[PredictionId("P-ADJ")]
    assert stored.adjudication_rationale == "OBS-002 at 14.8 matches predicted 15.0 within 1-sigma"


# ── Observation transition guards ─────────────────────────────────


def test_observation_retracted_is_terminal(base_graph):
    """RETRACTED observations cannot be re-transitioned."""
    graph = base_graph.transition_observation(
        ObservationId("OBS-001"), ObservationStatus.RETRACTED
    )
    with pytest.raises(InvariantViolation, match="Cannot transition"):
        graph.transition_observation(
            ObservationId("OBS-001"), ObservationStatus.PRELIMINARY
        )


def test_observation_validated_to_disputed(base_graph):
    """VALIDATED observations can transition to DISPUTED."""
    graph = base_graph.transition_observation(
        ObservationId("OBS-002"), ObservationStatus.DISPUTED
    )
    assert graph.observations[ObservationId("OBS-002")].status == ObservationStatus.DISPUTED


def test_observation_disputed_to_validated(base_graph):
    """DISPUTED observations can transition back to VALIDATED (dispute resolved)."""
    graph = base_graph.transition_observation(
        ObservationId("OBS-001"), ObservationStatus.DISPUTED
    )
    graph = graph.transition_observation(
        ObservationId("OBS-001"), ObservationStatus.VALIDATED
    )
    assert graph.observations[ObservationId("OBS-001")].status == ObservationStatus.VALIDATED


# ── Discovery transition guards ───────────────────────────────────


def test_discovery_archived_is_terminal(base_graph):
    """ARCHIVED discoveries cannot be re-transitioned."""
    from datetime import date
    from episteme.epistemic.model import Discovery, DiscoveryId

    graph = base_graph.register_discovery(
        Discovery(
            id=DiscoveryId("D-001"),
            title="Unexpected catalytic activity",
            date=date(2026, 4, 10),
            summary="Found unexpected activity",
            impact="Opens new research direction",
            status=DiscoveryStatus.NEW,
        )
    )
    graph = graph.transition_discovery(DiscoveryId("D-001"), DiscoveryStatus.ARCHIVED)
    with pytest.raises(InvariantViolation, match="Cannot transition"):
        graph.transition_discovery(DiscoveryId("D-001"), DiscoveryStatus.NEW)


def test_discovery_new_to_integrated(base_graph):
    """NEW discoveries can transition to INTEGRATED."""
    from datetime import date
    from episteme.epistemic.model import Discovery, DiscoveryId

    graph = base_graph.register_discovery(
        Discovery(
            id=DiscoveryId("D-001"),
            title="Unexpected result",
            date=date(2026, 4, 10),
            summary="Found unexpected pattern",
            impact="Suggests new hypothesis",
            status=DiscoveryStatus.NEW,
        )
    )
    graph = graph.transition_discovery(DiscoveryId("D-001"), DiscoveryStatus.INTEGRATED)
    assert graph.discoveries[DiscoveryId("D-001")].status == DiscoveryStatus.INTEGRATED


# ── Dead end transition guards ────────────────────────────────────


def test_dead_end_archived_is_terminal(base_graph):
    """ARCHIVED dead ends cannot be re-transitioned."""
    from episteme.epistemic.model import DeadEnd, DeadEndId

    graph = base_graph.register_dead_end(
        DeadEnd(
            id=DeadEndId("DE-001"),
            title="Failed approach A",
            description="Tried X, didn't work because Y",
            status=DeadEndStatus.ACTIVE,
        )
    )
    graph = graph.transition_dead_end(DeadEndId("DE-001"), DeadEndStatus.ARCHIVED)
    with pytest.raises(InvariantViolation, match="Cannot transition"):
        graph.transition_dead_end(DeadEndId("DE-001"), DeadEndStatus.ACTIVE)


def test_dead_end_active_to_resolved(base_graph):
    """ACTIVE dead ends can transition to RESOLVED."""
    from episteme.epistemic.model import DeadEnd, DeadEndId

    graph = base_graph.register_dead_end(
        DeadEnd(
            id=DeadEndId("DE-001"),
            title="Failed approach A",
            description="Tried X, didn't work",
            status=DeadEndStatus.ACTIVE,
        )
    )
    graph = graph.transition_dead_end(DeadEndId("DE-001"), DeadEndStatus.RESOLVED)
    assert graph.dead_ends[DeadEndId("DE-001")].status == DeadEndStatus.RESOLVED
