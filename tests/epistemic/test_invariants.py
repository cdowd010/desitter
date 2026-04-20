"""Tests for on-demand semantic invariant validators."""
from __future__ import annotations

from episteme.epistemic.model import (
    Assumption,
    AssumptionId,
    AssumptionType,
    DeadEnd,
    DeadEndId,
    DeadEndStatus,
    Discovery,
    DiscoveryId,
    DiscoveryStatus,
    Hypothesis,
    HypothesisId,
    HypothesisStatus,
    HypothesisType,
    Observation,
    ObservationId,
    ObservationStatus,
    Objective,
    ObjectiveId,
    ObjectiveKind,
    ObjectiveStatus,
    Prediction,
    PredictionId,
    PredictionStatus,
)
from episteme.epistemic.invariants import (
    validate_all,
    validate_adjudication_has_observations,
    validate_adjudication_rationale,
    validate_compromised_observation_basis,
    validate_deferred_hypothesis_active_predictions,
    validate_disconnected_dead_ends,
    validate_discovery_integration_consistency,
    validate_evidence_consistency,
    validate_falsified_assumption_impact,
    validate_goal_objective_criteria,
    validate_hypothesis_empirical_interface,
    validate_hypothesis_refutation_criteria,
    validate_observed_but_pending,
    validate_orphaned_predictions,
    validate_prediction_transition,
    validate_refutation_criteria,
    validate_retracted_hypothesis_citations,
    validate_supersession_chains,
    validate_supersession_cycles,
    validate_supersession_status_consistency,
    validate_testability_regime_consistency,
)
from episteme.epistemic.types import (
    AssumptionStatus,
    ConfidenceTier,
    EvidenceKind,
    MeasurementRegime,
    Severity,
)


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
    """A RETRACTED hypothesis without superseded_by is OK — retraction may not have a successor."""
    graph = base_graph.transition_hypothesis(
        HypothesisId("C-001"), HypothesisStatus.RETRACTED
    )
    findings = validate_supersession_chains(graph)
    c001_warnings = [
        f for f in findings
        if f.severity == Severity.WARNING and "C-001" in f.source
    ]
    assert c001_warnings == []


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
    """supersedes pointing to a non-existent prediction is now blocked at registration."""
    from episteme.epistemic.errors import BrokenReferenceError
    import pytest

    with pytest.raises(BrokenReferenceError, match="P-999"):
        base_graph.register_prediction(
            Prediction(
                id=PredictionId("P-002"),
                observable="yield",
                predicted=0.20,
                status=PredictionStatus.PENDING,
                supersedes=PredictionId("P-999"),
            )
        )


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


# ── Testability / regime consistency ──────────────────────────────


def test_not_yet_testable_with_measured_regime(base_graph):
    """NOT_YET_TESTABLE + MEASURED regime is a contradictory combination."""
    graph = base_graph.register_prediction(
        Prediction(
            id=PredictionId("P-NYT"),
            observable="dark matter flux",
            predicted=42,
            status=PredictionStatus.NOT_YET_TESTABLE,
            measurement_regime=MeasurementRegime.MEASURED,
        )
    )
    findings = validate_testability_regime_consistency(graph)
    assert any("NOT_YET_TESTABLE" in f.message and "P-NYT" in f.source for f in findings)


def test_not_yet_testable_with_unmeasured_is_fine(base_graph):
    """NOT_YET_TESTABLE + UNMEASURED is the expected pairing — no finding."""
    graph = base_graph.register_prediction(
        Prediction(
            id=PredictionId("P-NYT"),
            observable="dark matter flux",
            predicted=42,
            status=PredictionStatus.NOT_YET_TESTABLE,
            measurement_regime=MeasurementRegime.UNMEASURED,
        )
    )
    findings = validate_testability_regime_consistency(graph)
    assert not findings


# ── Goal objective criteria ───────────────────────────────────────


def test_goal_objective_missing_success_criteria(base_graph):
    """A GOAL objective without success_criteria triggers a WARNING."""
    graph = base_graph.register_objective(
        Objective(
            id=ObjectiveId("OBJ-GOAL"),
            title="Reduce latency by 50%",
            kind=ObjectiveKind.GOAL,
            status=ObjectiveStatus.ACTIVE,
        )
    )
    findings = validate_goal_objective_criteria(graph)
    assert any("success_criteria" in f.message and "OBJ-GOAL" in f.source for f in findings)


def test_goal_objective_with_success_criteria_is_fine(base_graph):
    """A GOAL objective with success_criteria produces no finding."""
    graph = base_graph.register_objective(
        Objective(
            id=ObjectiveId("OBJ-GOAL"),
            title="Reduce latency by 50%",
            kind=ObjectiveKind.GOAL,
            status=ObjectiveStatus.ACTIVE,
            success_criteria="p99 latency < 50ms over 7 days",
        )
    )
    findings = validate_goal_objective_criteria(graph)
    assert not findings


# ── Retracted citation severity downgrade ─────────────────────────


def test_retracted_citation_terminal_prediction_downgraded(base_graph):
    """A REFUTED prediction citing a retracted hypothesis should be INFO, not CRITICAL."""
    # P-001 is MEASURED — must record observed value before adjudication
    old = base_graph.predictions[PredictionId("P-001")]
    updated = Prediction(
        id=old.id,
        observable=old.observable,
        predicted=old.predicted,
        observed=0.01,
        tier=old.tier,
        evidence_kind=old.evidence_kind,
        measurement_regime=old.measurement_regime,
        hypothesis_ids=old.hypothesis_ids,
        stress_criteria=old.stress_criteria,
    )
    graph = base_graph.update_prediction(updated)
    graph = graph.transition_hypothesis(
        HypothesisId("C-001"), HypothesisStatus.RETRACTED
    )
    graph = graph.transition_prediction(
        PredictionId("P-001"), PredictionStatus.REFUTED
    )
    findings = validate_retracted_hypothesis_citations(graph)
    pred_findings = [f for f in findings if "P-001" in f.source]
    assert pred_findings
    assert all(f.severity == Severity.INFO for f in pred_findings)


def test_retracted_citation_active_prediction_is_critical(base_graph):
    """A PENDING prediction citing a retracted hypothesis should remain CRITICAL."""
    graph = base_graph.transition_hypothesis(
        HypothesisId("C-001"), HypothesisStatus.RETRACTED
    )
    findings = validate_retracted_hypothesis_citations(graph)
    pred_findings = [f for f in findings if "P-001" in f.source]
    assert pred_findings
    assert all(f.severity == Severity.CRITICAL for f in pred_findings)


# ── Evidence consistency: FIT_CHECK + RETRODICTION ────────────────


def test_fit_check_retrodiction_is_contradictory(base_graph):
    """FIT_CHECK + RETRODICTION is now blocked at registration (Tier 1 guard)."""
    from episteme.epistemic.errors import InvariantViolation
    import pytest

    with pytest.raises(InvariantViolation, match="FIT_CHECK"):
        base_graph.register_prediction(
            Prediction(
                id=PredictionId("P-FIT"),
                observable="historical data",
                predicted=1.0,
                tier=ConfidenceTier.FIT_CHECK,
                evidence_kind=EvidenceKind.RETRODICTION,
            )
        )


def test_fit_check_fit_consistency_is_fine(base_graph):
    """FIT_CHECK + FIT_CONSISTENCY is the valid pairing — no finding."""
    graph = base_graph.register_prediction(
        Prediction(
            id=PredictionId("P-FIT"),
            observable="calibration data",
            predicted=1.0,
            tier=ConfidenceTier.FIT_CHECK,
            evidence_kind=EvidenceKind.FIT_CONSISTENCY,
        )
    )
    findings = validate_evidence_consistency(graph)
    fit_findings = [f for f in findings if "P-FIT" in f.source]
    assert not fit_findings


# ── Compromised observation basis ─────────────────────────────────


def test_confirmed_prediction_with_disputed_observation(base_graph):
    """A CONFIRMED prediction with a DISPUTED observation triggers WARNING."""
    from datetime import date
    # P-001 is MEASURED — must record observed value before adjudication
    old = base_graph.predictions[PredictionId("P-001")]
    updated = Prediction(
        id=old.id,
        observable=old.observable,
        predicted=old.predicted,
        observed=0.14,
        tier=old.tier,
        evidence_kind=old.evidence_kind,
        measurement_regime=old.measurement_regime,
        hypothesis_ids=old.hypothesis_ids,
        stress_criteria=old.stress_criteria,
        observations=old.observations,
    )
    graph = base_graph.update_prediction(updated)
    graph = graph.transition_prediction(
        PredictionId("P-001"), PredictionStatus.CONFIRMED
    )
    # OBS-002 is linked to P-001 and VALIDATED; dispute it
    graph = graph.transition_observation(
        ObservationId("OBS-002"), ObservationStatus.DISPUTED
    )
    findings = validate_compromised_observation_basis(graph)
    assert any("P-001" in f.source and "disputed/retracted" in f.message for f in findings)


def test_pending_prediction_with_disputed_obs_no_finding(base_graph):
    """PENDING predictions are not flagged even if observations are disputed."""
    graph = base_graph.transition_observation(
        ObservationId("OBS-002"), ObservationStatus.DISPUTED
    )
    findings = validate_compromised_observation_basis(graph)
    pred_findings = [f for f in findings if "P-001" in f.source]
    assert not pred_findings


# ── Supersession status consistency ───────────────────────────────


def test_superseded_prediction_without_successor(base_graph):
    """A SUPERSEDED prediction with no successor triggers WARNING."""
    graph = base_graph.transition_prediction(
        PredictionId("P-001"), PredictionStatus.SUPERSEDED
    )
    findings = validate_supersession_status_consistency(graph)
    assert any("no successor" in f.message and "P-001" in f.source for f in findings)


def test_successor_auto_supersedes_predecessor(base_graph):
    """Registering B with supersedes=A auto-transitions A to SUPERSEDED."""
    graph = base_graph.register_prediction(
        Prediction(
            id=PredictionId("P-002"),
            observable="yield v2",
            predicted=0.20,
            supersedes=PredictionId("P-001"),
        )
    )
    assert graph.predictions[PredictionId("P-001")].status == PredictionStatus.SUPERSEDED
    findings = validate_supersession_status_consistency(graph)
    p001_findings = [f for f in findings if "P-001" in f.source]
    assert not p001_findings


def test_valid_supersession_status_no_findings(base_graph):
    """A correctly superseded prediction pair produces no findings."""
    graph = base_graph.register_prediction(
        Prediction(
            id=PredictionId("P-002"),
            observable="yield v2",
            predicted=0.20,
            supersedes=PredictionId("P-001"),
        )
    )
    findings = validate_supersession_status_consistency(graph)
    assert not findings


# ── Refutation criteria ───────────────────────────────────────────


def test_refuted_without_refutation_criteria(base_graph):
    """A REFUTED prediction with no refutation_criteria triggers WARNING."""
    graph = base_graph.register_prediction(
        Prediction(
            id=PredictionId("P-NORC"),
            observable="mass",
            predicted=5.0,
            status=PredictionStatus.REFUTED,
        )
    )
    findings = validate_refutation_criteria(graph)
    assert any("P-NORC" in f.source and "refutation_criteria" in f.message for f in findings)


def test_refuted_with_refutation_criteria_is_fine(base_graph):
    """A REFUTED prediction with refutation_criteria produces no finding."""
    graph = base_graph.register_prediction(
        Prediction(
            id=PredictionId("P-RC"),
            observable="mass",
            predicted=5.0,
            status=PredictionStatus.REFUTED,
            refutation_criteria="observed > 2 sigma from predicted",
        )
    )
    findings = validate_refutation_criteria(graph)
    rc_findings = [f for f in findings if "P-RC" in f.source]
    assert not rc_findings


# ── Observed but pending ──────────────────────────────────────────


def test_observed_but_pending_triggers_info(base_graph):
    """A PENDING prediction with observed data triggers INFO."""
    graph = base_graph.register_prediction(
        Prediction(
            id=PredictionId("P-OBS"),
            observable="temperature",
            predicted=300,
            status=PredictionStatus.PENDING,
            observed=298,
        )
    )
    findings = validate_observed_but_pending(graph)
    assert any("P-OBS" in f.source and f.severity == Severity.INFO for f in findings)


def test_pending_without_observed_is_fine(base_graph):
    """A PENDING prediction without observed data produces no finding."""
    findings = validate_observed_but_pending(base_graph)
    pending_findings = [f for f in findings if "P-001" in f.source]
    assert not pending_findings


# ── Deferred hypothesis with active predictions ──────────────────


def test_deferred_hypothesis_with_active_predictions(base_graph):
    """A DEFERRED hypothesis with PENDING predictions triggers WARNING."""
    graph = base_graph.transition_hypothesis(
        HypothesisId("C-001"), HypothesisStatus.DEFERRED
    )
    findings = validate_deferred_hypothesis_active_predictions(graph)
    assert any("C-001" in f.source and "active prediction" in f.message for f in findings)


def test_deferred_hypothesis_no_active_predictions_is_fine(base_graph):
    """A DEFERRED hypothesis whose predictions are all terminal produces no finding."""
    # P-001 is MEASURED — must record observed value before adjudication
    old = base_graph.predictions[PredictionId("P-001")]
    updated = Prediction(
        id=old.id,
        observable=old.observable,
        predicted=old.predicted,
        observed=0.01,
        tier=old.tier,
        evidence_kind=old.evidence_kind,
        measurement_regime=old.measurement_regime,
        hypothesis_ids=old.hypothesis_ids,
        stress_criteria=old.stress_criteria,
    )
    graph = base_graph.update_prediction(updated)
    graph = graph.transition_prediction(
        PredictionId("P-001"), PredictionStatus.REFUTED
    )
    graph = graph.transition_hypothesis(
        HypothesisId("C-001"), HypothesisStatus.DEFERRED
    )
    findings = validate_deferred_hypothesis_active_predictions(graph)
    assert not findings


# ── Orphaned predictions ─────────────────────────────────────────


def test_orphaned_prediction_triggers_info(base_graph):
    """A prediction with no hypothesis_ids triggers INFO."""
    graph = base_graph.register_prediction(
        Prediction(
            id=PredictionId("P-ORPHAN"),
            observable="unknown",
            predicted=0,
        )
    )
    findings = validate_orphaned_predictions(graph)
    assert any("P-ORPHAN" in f.source and "no hypothesis_ids" in f.message for f in findings)


def test_prediction_with_hypothesis_ids_is_fine(base_graph):
    """A prediction with hypothesis_ids produces no orphan finding."""
    findings = validate_orphaned_predictions(base_graph)
    p001_findings = [f for f in findings if "P-001" in f.source]
    assert not p001_findings


# ── Tier 2: validate_prediction_transition ─────────────────────────


def test_transition_stressed_without_stress_criteria_warns(base_graph):
    """Transitioning to STRESSED without stress_criteria produces a warning."""
    # Register a prediction without stress_criteria
    graph = base_graph.register_prediction(
        Prediction(
            id=PredictionId("P-NO-SC"),
            observable="x",
            predicted=1.0,
            measurement_regime=MeasurementRegime.UNMEASURED,
            hypothesis_ids={HypothesisId("C-001")},
        )
    )
    findings = validate_prediction_transition(graph, "P-NO-SC", PredictionStatus.STRESSED)
    assert any("stress_criteria" in f.message for f in findings)
    assert all(f.severity == Severity.WARNING for f in findings)


def test_transition_stressed_with_stress_criteria_clean(base_graph):
    """Transitioning to STRESSED with stress_criteria produces no warning."""
    findings = validate_prediction_transition(base_graph, "P-001", PredictionStatus.STRESSED)
    stressed_findings = [f for f in findings if "stress_criteria" in f.message]
    assert not stressed_findings


def test_transition_refuted_without_refutation_criteria_warns(base_graph):
    """Transitioning to REFUTED without refutation_criteria produces a warning."""
    graph = base_graph.register_prediction(
        Prediction(
            id=PredictionId("P-NO-RC"),
            observable="x",
            predicted=1.0,
            measurement_regime=MeasurementRegime.UNMEASURED,
            hypothesis_ids={HypothesisId("C-001")},
        )
    )
    findings = validate_prediction_transition(graph, "P-NO-RC", PredictionStatus.REFUTED)
    assert any("refutation_criteria" in f.message for f in findings)


def test_transition_not_yet_testable_with_measured_warns(base_graph):
    """NOT_YET_TESTABLE + MEASURED regime produces a warning."""
    findings = validate_prediction_transition(
        base_graph, "P-001", PredictionStatus.NOT_YET_TESTABLE
    )
    assert any("NOT_YET_TESTABLE" in f.message for f in findings)


def test_transition_not_yet_testable_with_unmeasured_clean(base_graph):
    """NOT_YET_TESTABLE + UNMEASURED regime produces no warning."""
    graph = base_graph.register_prediction(
        Prediction(
            id=PredictionId("P-UNM"),
            observable="x",
            predicted=1.0,
            measurement_regime=MeasurementRegime.UNMEASURED,
            hypothesis_ids={HypothesisId("C-001")},
        )
    )
    findings = validate_prediction_transition(
        graph, "P-UNM", PredictionStatus.NOT_YET_TESTABLE
    )
    assert not findings


def test_transition_confirmed_produces_no_tier2_warnings(base_graph):
    """CONFIRMED transition has no Tier 2 warnings (Tier 1 guards handle it)."""
    findings = validate_prediction_transition(
        base_graph, "P-001", PredictionStatus.CONFIRMED
    )
    assert not findings


def test_transition_nonexistent_prediction_returns_empty(base_graph):
    """Nonexistent prediction ID returns empty findings."""
    findings = validate_prediction_transition(
        base_graph, "P-NOPE", PredictionStatus.STRESSED
    )
    assert findings == []


# ── Falsified assumption impact ───────────────────────────────────


def test_falsified_assumption_impacts_hypothesis(base_graph):
    """FALSIFIED assumption triggers CRITICAL on active hypotheses referencing it."""
    graph = base_graph.transition_assumption(
        AssumptionId("A-001"), AssumptionStatus.FALSIFIED
    )
    findings = validate_falsified_assumption_impact(graph)
    critical = [f for f in findings if f.severity == Severity.CRITICAL]
    assert any("C-001" in f.source and "falsified" in f.message for f in critical)


def test_questioned_assumption_impacts_hypothesis(base_graph):
    """QUESTIONED assumption triggers WARNING on active hypotheses referencing it."""
    graph = base_graph.transition_assumption(
        AssumptionId("A-001"), AssumptionStatus.QUESTIONED
    )
    findings = validate_falsified_assumption_impact(graph)
    warnings = [f for f in findings if f.severity == Severity.WARNING]
    assert any("C-001" in f.source and "questioned" in f.message for f in warnings)


def test_falsified_assumption_impacts_conditional_predictions(base_graph):
    """FALSIFIED assumption triggers CRITICAL on predictions conditional on it."""
    # Register a prediction conditional on A-001
    pred = Prediction(
        id=PredictionId("P-COND"),
        observable="conditional test",
        predicted=1.0,
        measurement_regime=MeasurementRegime.MEASURED,
        conditional_on={AssumptionId("A-001")},
    )
    graph = base_graph.register_prediction(pred)
    graph = graph.transition_assumption(
        AssumptionId("A-001"), AssumptionStatus.FALSIFIED
    )
    findings = validate_falsified_assumption_impact(graph)
    critical = [f for f in findings if f.severity == Severity.CRITICAL]
    assert any("P-COND" in f.source and "conditional" in f.message for f in critical)


def test_active_assumptions_produce_no_impact_findings(base_graph):
    """ACTIVE assumptions produce no findings from falsified assumption validator."""
    findings = validate_falsified_assumption_impact(base_graph)
    assert findings == []


# ── Adjudication without observations ─────────────────────────────


def test_adjudicated_without_observations_warning(base_graph):
    """CONFIRMED prediction with no observations triggers WARNING."""
    # P-001 has one observation (OBS-002), so we need a fresh prediction
    pred = Prediction(
        id=PredictionId("P-NOOBS"),
        observable="yield",
        predicted=0.15,
        observed=0.14,
        measurement_regime=MeasurementRegime.MEASURED,
        hypothesis_ids={HypothesisId("C-001")},
    )
    graph = base_graph.register_prediction(pred)
    graph = graph.transition_prediction(PredictionId("P-NOOBS"), PredictionStatus.CONFIRMED)
    findings = validate_adjudication_has_observations(graph)
    warnings = [f for f in findings if "P-NOOBS" in f.source]
    assert len(warnings) == 1
    assert "no linked observations" in warnings[0].message


def test_adjudicated_with_observations_no_warning(base_graph):
    """CONFIRMED prediction linked to observations produces no finding."""
    # P-001 already has OBS-002 linked; set observed so transition is allowed
    p001 = base_graph.predictions[PredictionId("P-001")]
    updated = Prediction(
        id=p001.id,
        observable=p001.observable,
        predicted=p001.predicted,
        observed=0.14,
        status=p001.status,
        tier=p001.tier,
        evidence_kind=p001.evidence_kind,
        measurement_regime=p001.measurement_regime,
        hypothesis_ids=p001.hypothesis_ids,
        stress_criteria=p001.stress_criteria,
        observations=p001.observations,
    )
    graph = base_graph.update_prediction(updated)
    graph = graph.transition_prediction(PredictionId("P-001"), PredictionStatus.CONFIRMED)
    findings = validate_adjudication_has_observations(graph)
    p001_findings = [f for f in findings if "P-001" in f.source]
    assert p001_findings == []


def test_adjudicated_unmeasured_exempt(base_graph):
    """UNMEASURED prediction exempt from observation requirement."""
    pred = Prediction(
        id=PredictionId("P-UNM"),
        observable="unobservable",
        predicted="yes",
        measurement_regime=MeasurementRegime.UNMEASURED,
    )
    graph = base_graph.register_prediction(pred)
    graph = graph.transition_prediction(PredictionId("P-UNM"), PredictionStatus.CONFIRMED)
    findings = validate_adjudication_has_observations(graph)
    unm_findings = [f for f in findings if "P-UNM" in f.source]
    assert unm_findings == []


# ── Adjudication rationale ────────────────────────────────────────


def test_adjudicated_without_rationale_warning(base_graph):
    """CONFIRMED prediction without adjudication_rationale triggers WARNING."""
    # Need observed value to allow CONFIRMED transition
    pred = Prediction(
        id=PredictionId("P-NORAT"),
        observable="yield",
        predicted=0.15,
        observed=0.14,
        measurement_regime=MeasurementRegime.MEASURED,
        hypothesis_ids={HypothesisId("C-001")},
        # No adjudication_rationale
    )
    graph = base_graph.register_prediction(pred)
    graph = graph.transition_prediction(PredictionId("P-NORAT"), PredictionStatus.CONFIRMED)
    findings = validate_adjudication_rationale(graph)
    warnings = [f for f in findings if "P-NORAT" in f.source]
    assert len(warnings) == 1
    assert "adjudication_rationale" in warnings[0].message


def test_adjudicated_with_rationale_no_warning(base_graph):
    """CONFIRMED prediction with adjudication_rationale produces no finding."""
    pred = Prediction(
        id=PredictionId("P-RAT"),
        observable="yield",
        predicted=0.15,
        observed=0.14,
        measurement_regime=MeasurementRegime.MEASURED,
        hypothesis_ids={HypothesisId("C-001")},
        adjudication_rationale="OBS-002 at 14.8 matches within 1-sigma",
    )
    graph = base_graph.register_prediction(pred)
    graph = graph.transition_prediction(PredictionId("P-RAT"), PredictionStatus.CONFIRMED)
    findings = validate_adjudication_rationale(graph)
    rat_findings = [f for f in findings if "P-RAT" in f.source]
    assert rat_findings == []


def test_pending_without_rationale_no_warning(base_graph):
    """PENDING prediction without rationale produces no finding."""
    findings = validate_adjudication_rationale(base_graph)
    p001_findings = [f for f in findings if "P-001" in f.source]
    assert p001_findings == []


# ── Hypothesis refutation criteria maturity ───────────────────────


def test_mature_hypothesis_without_refutation_criteria(base_graph):
    """Active hypothesis with predictions but no refutation_criteria triggers INFO."""
    # C-001 has refutation_criteria in base_graph, so add one without
    from episteme.epistemic.model import Assumption, AssumptionType
    graph = base_graph.register_assumption(
        Assumption(
            id=AssumptionId("A-002"),
            statement="Second assumption",
            type=AssumptionType.EMPIRICAL,
        )
    )
    graph = graph.register_hypothesis(
        Hypothesis(
            id=HypothesisId("C-002"),
            statement="Alternative catalyst pathway",
            type=HypothesisType.DERIVED,
            depends_on={HypothesisId("C-001")},
            # No refutation_criteria
        )
    )
    graph = graph.register_prediction(
        Prediction(
            id=PredictionId("P-MAT"),
            observable="selectivity",
            predicted=0.9,
            hypothesis_ids={HypothesisId("C-002")},
        )
    )
    findings = validate_hypothesis_refutation_criteria(graph)
    info = [f for f in findings if "C-002" in f.source]
    assert len(info) == 1
    assert info[0].severity == Severity.INFO


def test_hypothesis_with_refutation_criteria_no_finding(base_graph):
    """Hypothesis with refutation_criteria produces no finding (C-001 has it)."""
    findings = validate_hypothesis_refutation_criteria(base_graph)
    c001_findings = [f for f in findings if "C-001" in f.source]
    assert c001_findings == []


def test_hypothesis_without_predictions_no_finding(base_graph):
    """Active hypothesis with no predictions is not flagged (it's immature)."""
    graph = base_graph.register_hypothesis(
        Hypothesis(
            id=HypothesisId("C-EARLY"),
            statement="Early-stage hypothesis",
            type=HypothesisType.DERIVED,
            depends_on={HypothesisId("C-001")},
            # No refutation_criteria, but also no predictions yet
        )
    )
    findings = validate_hypothesis_refutation_criteria(graph)
    early_findings = [f for f in findings if "C-EARLY" in f.source]
    assert early_findings == []


# ── Fix: RETRACTED hypothesis superseded_by no longer warns ───────


def test_retracted_hypothesis_no_superseded_by_is_ok(base_graph):
    """RETRACTED hypothesis without superseded_by produces no WARNING."""
    graph = base_graph.transition_hypothesis(
        HypothesisId("C-001"), HypothesisStatus.RETRACTED,
    )
    findings = validate_supersession_chains(graph)
    c001_warnings = [
        f for f in findings
        if "C-001" in f.source and f.severity == Severity.WARNING
    ]
    assert c001_warnings == []


def test_revised_hypothesis_no_superseded_by_warns(base_graph):
    """REVISED hypothesis without superseded_by still produces WARNING."""
    graph = base_graph.transition_hypothesis(
        HypothesisId("C-001"), HypothesisStatus.REVISED,
    )
    findings = validate_supersession_chains(graph)
    c001_warnings = [
        f for f in findings
        if "C-001" in f.source and f.severity == Severity.WARNING
    ]
    assert len(c001_warnings) == 1
    assert "REVISED" in c001_warnings[0].message


# ── Discovery integration consistency ─────────────────────────────


def test_integrated_discovery_without_links_warns(base_graph):
    """INTEGRATED discovery with no related entities triggers WARNING."""
    from datetime import date
    graph = base_graph.register_discovery(
        Discovery(
            id=DiscoveryId("D-001"),
            title="Spurious catalyst effect",
            date=date(2026, 5, 1),
            summary="Unexpected side reaction observed",
            impact="May affect yield predictions",
            status=DiscoveryStatus.INTEGRATED,
            # No related_hypotheses, no related_predictions
        )
    )
    findings = validate_discovery_integration_consistency(graph)
    assert len(findings) == 1
    assert findings[0].severity == Severity.WARNING
    assert "D-001" in findings[0].source
    assert "unsubstantiated" in findings[0].message


def test_integrated_discovery_with_links_no_finding(base_graph):
    """INTEGRATED discovery with hypothesis links produces no finding."""
    from datetime import date
    graph = base_graph.register_discovery(
        Discovery(
            id=DiscoveryId("D-002"),
            title="Catalyst selectivity",
            date=date(2026, 5, 1),
            summary="Selectivity pattern found",
            impact="Refines hypothesis",
            status=DiscoveryStatus.INTEGRATED,
            related_hypotheses={HypothesisId("C-001")},
        )
    )
    findings = validate_discovery_integration_consistency(graph)
    d002 = [f for f in findings if "D-002" in f.source]
    assert d002 == []


def test_new_discovery_without_links_no_finding(base_graph):
    """NEW discovery without links is not flagged (only INTEGRATED matters)."""
    from datetime import date
    graph = base_graph.register_discovery(
        Discovery(
            id=DiscoveryId("D-003"),
            title="Preliminary finding",
            date=date(2026, 5, 1),
            summary="Something interesting",
            impact="TBD",
            status=DiscoveryStatus.NEW,
        )
    )
    findings = validate_discovery_integration_consistency(graph)
    d003 = [f for f in findings if "D-003" in f.source]
    assert d003 == []


# ── Supersession cycle detection ──────────────────────────────────


def test_prediction_supersession_cycle_detected(base_graph):
    """A prediction supersession cycle is flagged CRITICAL."""
    # Create P-002 superseding P-001, then manually create a cycle by
    # updating P-001 to supersede P-002
    graph = base_graph.register_prediction(
        Prediction(
            id=PredictionId("P-002"),
            observable="yield v2",
            predicted=0.20,
            hypothesis_ids={HypothesisId("C-001")},
            supersedes=PredictionId("P-001"),
        )
    )
    # Force cycle by updating P-001 to supersede P-002
    from copy import deepcopy
    p001 = deepcopy(graph.predictions[PredictionId("P-001")])
    p001.supersedes = PredictionId("P-002")
    graph = graph.update_prediction(p001)
    findings = validate_supersession_cycles(graph)
    cycle_findings = [
        f for f in findings
        if f.severity == Severity.CRITICAL and "cycle" in f.message.lower()
    ]
    assert len(cycle_findings) >= 1


def test_linear_supersession_chain_no_finding(base_graph):
    """A linear supersession chain produces no finding."""
    graph = base_graph.register_prediction(
        Prediction(
            id=PredictionId("P-002"),
            observable="yield v2",
            predicted=0.20,
            hypothesis_ids={HypothesisId("C-001")},
            supersedes=PredictionId("P-001"),
        )
    )
    graph = graph.register_prediction(
        Prediction(
            id=PredictionId("P-003"),
            observable="yield v3",
            predicted=0.25,
            hypothesis_ids={HypothesisId("C-001")},
            supersedes=PredictionId("P-002"),
        )
    )
    findings = validate_supersession_cycles(graph)
    assert findings == []


def test_hypothesis_supersession_cycle_detected(base_graph):
    """A hypothesis superseded_by cycle is flagged CRITICAL."""
    # Register two hypotheses that point at each other via superseded_by
    graph = base_graph.register_hypothesis(
        Hypothesis(
            id=HypothesisId("C-X"),
            statement="Hypothesis X",
            type=HypothesisType.DERIVED,
            depends_on={HypothesisId("C-001")},
            superseded_by=HypothesisId("C-001"),
        )
    )
    # Update C-001 to point back at C-X
    from copy import deepcopy
    c001 = deepcopy(graph.hypotheses[HypothesisId("C-001")])
    c001.superseded_by = HypothesisId("C-X")
    graph = graph.update_hypothesis(c001)
    findings = validate_supersession_cycles(graph)
    cycle_findings = [
        f for f in findings
        if f.severity == Severity.CRITICAL and "cycle" in f.message.lower()
    ]
    assert len(cycle_findings) >= 1


# ── Hypothesis empirical interface ────────────────────────────────


def test_active_hypothesis_without_predictions_flagged(base_graph):
    """Active hypothesis with no predictions triggers INFO."""
    graph = base_graph.register_hypothesis(
        Hypothesis(
            id=HypothesisId("C-LONELY"),
            statement="Lonely hypothesis with no predictions",
            type=HypothesisType.DERIVED,
            depends_on={HypothesisId("C-001")},
        )
    )
    findings = validate_hypothesis_empirical_interface(graph)
    lonely = [f for f in findings if "C-LONELY" in f.source]
    assert len(lonely) == 1
    assert lonely[0].severity == Severity.INFO
    assert "no predictions" in lonely[0].message


def test_active_hypothesis_with_predictions_no_finding(base_graph):
    """C-001 has predictions — no finding expected."""
    findings = validate_hypothesis_empirical_interface(base_graph)
    c001 = [f for f in findings if "C-001" in f.source]
    assert c001 == []


def test_deferred_hypothesis_without_predictions_not_flagged(base_graph):
    """DEFERRED hypothesis without predictions is not flagged."""
    graph = base_graph.register_hypothesis(
        Hypothesis(
            id=HypothesisId("C-DEF"),
            statement="Deferred hypothesis",
            type=HypothesisType.DERIVED,
            status=HypothesisStatus.DEFERRED,
            depends_on={HypothesisId("C-001")},
        )
    )
    findings = validate_hypothesis_empirical_interface(graph)
    deferred = [f for f in findings if "C-DEF" in f.source]
    assert deferred == []


# ── Disconnected dead ends ────────────────────────────────────────


def test_disconnected_dead_end_flagged(base_graph):
    """Dead end with no links triggers INFO."""
    graph = base_graph.register_dead_end(
        DeadEnd(
            id=DeadEndId("DE-001"),
            title="Failed approach",
            description="Tried X but it didn't work",
            status=DeadEndStatus.ACTIVE,
            # No related_hypotheses, no related_predictions
        )
    )
    findings = validate_disconnected_dead_ends(graph)
    assert len(findings) == 1
    assert findings[0].severity == Severity.INFO
    assert "DE-001" in findings[0].source


def test_linked_dead_end_no_finding(base_graph):
    """Dead end with hypothesis link produces no finding."""
    graph = base_graph.register_dead_end(
        DeadEnd(
            id=DeadEndId("DE-002"),
            title="Failed catalyst approach",
            description="Didn't work because of side reactions",
            status=DeadEndStatus.ACTIVE,
            related_hypotheses={HypothesisId("C-001")},
        )
    )
    findings = validate_disconnected_dead_ends(graph)
    de002 = [f for f in findings if "DE-002" in f.source]
    assert de002 == []


def test_dead_end_with_prediction_link_no_finding(base_graph):
    """Dead end with prediction link produces no finding."""
    graph = base_graph.register_dead_end(
        DeadEnd(
            id=DeadEndId("DE-003"),
            title="Refuted prediction path",
            description="Prediction P-001 path exhausted",
            status=DeadEndStatus.ACTIVE,
            related_predictions={PredictionId("P-001")},
        )
    )
    findings = validate_disconnected_dead_ends(graph)
    de003 = [f for f in findings if "DE-003" in f.source]
    assert de003 == []


# ── validate_experiment_coverage ─────────────────────────────────


def test_complete_experiment_no_observations_warns():
    """A COMPLETE experiment with no observations should produce a WARNING."""
    from episteme.epistemic.model import Experiment, ExperimentId
    from episteme.epistemic.invariants import validate_experiment_coverage
    from episteme.epistemic.types import ExperimentStatus
    from episteme.epistemic.graph import EpistemicGraph

    graph = EpistemicGraph()
    graph = graph.register_experiment(
        Experiment(id=ExperimentId("EXP-001"), title="Empty run", status=ExperimentStatus.PLANNED)
    )
    graph = graph.transition_experiment(ExperimentId("EXP-001"), ExperimentStatus.RUNNING)
    graph = graph.transition_experiment(ExperimentId("EXP-001"), ExperimentStatus.COMPLETE)
    findings = validate_experiment_coverage(graph)
    assert any("no recorded observations" in f.message for f in findings)
    assert findings[0].severity == Severity.WARNING


def test_complete_experiment_with_observations_no_finding():
    """A COMPLETE experiment with observations should not warn."""
    from datetime import date
    from episteme.epistemic.model import Experiment, ExperimentId
    from episteme.epistemic.invariants import validate_experiment_coverage
    from episteme.epistemic.types import ExperimentStatus
    from episteme.epistemic.graph import EpistemicGraph

    graph = EpistemicGraph()
    graph = graph.register_experiment(
        Experiment(id=ExperimentId("EXP-001"), title="Good run", status=ExperimentStatus.PLANNED)
    )
    graph = graph.transition_experiment(ExperimentId("EXP-001"), ExperimentStatus.RUNNING)
    graph = graph.transition_experiment(ExperimentId("EXP-001"), ExperimentStatus.COMPLETE)
    graph = graph.register_observation(
        Observation(
            id=ObservationId("OBS-001"),
            description="Measured output",
            value=3.14,
            date=date(2026, 4, 20),
            experiment=ExperimentId("EXP-001"),
        )
    )
    findings = validate_experiment_coverage(graph)
    no_obs = [f for f in findings if "no recorded observations" in f.message]
    assert no_obs == []


# ── validate_replicate_coherence ──────────────────────────────────


def test_replicate_of_abandoned_parent_warns():
    """Replicating an ABANDONED experiment should produce a WARNING."""
    from episteme.epistemic.model import Experiment, ExperimentId
    from episteme.epistemic.invariants import validate_replicate_coherence
    from episteme.epistemic.types import ExperimentStatus
    from episteme.epistemic.graph import EpistemicGraph

    graph = EpistemicGraph()
    graph = graph.register_experiment(
        Experiment(id=ExperimentId("EXP-001"), title="Original", status=ExperimentStatus.PLANNED)
    )
    graph = graph.transition_experiment(ExperimentId("EXP-001"), ExperimentStatus.ABANDONED)
    graph = graph.register_experiment(
        Experiment(
            id=ExperimentId("EXP-002"),
            title="Replicate",
            replicate_of=ExperimentId("EXP-001"),
        )
    )
    findings = validate_replicate_coherence(graph)
    assert any("ABANDONED" in f.message for f in findings)
    assert findings[0].severity == Severity.WARNING


def test_replicate_of_active_parent_no_finding():
    """Replicating a non-abandoned experiment should not produce a finding."""
    from episteme.epistemic.model import Experiment, ExperimentId
    from episteme.epistemic.invariants import validate_replicate_coherence
    from episteme.epistemic.graph import EpistemicGraph

    graph = EpistemicGraph()
    graph = graph.register_experiment(
        Experiment(id=ExperimentId("EXP-001"), title="Original")
    )
    graph = graph.register_experiment(
        Experiment(
            id=ExperimentId("EXP-002"),
            title="Replicate",
            replicate_of=ExperimentId("EXP-001"),
        )
    )
    findings = validate_replicate_coherence(graph)
    assert findings == []


def test_replicate_disjoint_predictions_warns():
    """Replicate with no overlapping predictions_tested should warn."""
    from episteme.epistemic.model import Experiment, ExperimentId
    from episteme.epistemic.invariants import validate_replicate_coherence
    from episteme.epistemic.graph import EpistemicGraph

    graph = EpistemicGraph()
    # Need two predictions to make them disjoint; reuse conftest fixture won't work
    # so build a minimal standalone graph
    from episteme.epistemic.model import (
        Hypothesis, HypothesisId, Prediction, PredictionId
    )
    graph = graph.register_hypothesis(
        Hypothesis(id=HypothesisId("H-A"), statement="H A")
    )
    graph = graph.register_hypothesis(
        Hypothesis(id=HypothesisId("H-B"), statement="H B")
    )
    graph = graph.register_prediction(
        Prediction(id=PredictionId("P-A"), observable="x", predicted=1,
                   hypothesis_ids={HypothesisId("H-A")})
    )
    graph = graph.register_prediction(
        Prediction(id=PredictionId("P-B"), observable="y", predicted=2,
                   hypothesis_ids={HypothesisId("H-B")})
    )
    graph = graph.register_experiment(
        Experiment(
            id=ExperimentId("EXP-001"),
            title="Original",
            predictions_tested={PredictionId("P-A")},
        )
    )
    graph = graph.register_experiment(
        Experiment(
            id=ExperimentId("EXP-002"),
            title="Replicate — wrong predictions",
            replicate_of=ExperimentId("EXP-001"),
            predictions_tested={PredictionId("P-B")},  # disjoint
        )
    )
    findings = validate_replicate_coherence(graph)
    assert any("no predictions_tested" in f.message for f in findings)
