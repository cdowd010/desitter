"""Validation rules that span multiple entities.

These require looking at the graph as a whole. Each function is pure:
(EpistemicGraph) -> list[Finding].

Structural invariants (refs exist, no cycles, bidirectional links) live
in graph.py and are enforced at mutation time.

Semantic/coverage invariants live here and are checked on demand.
"""
from __future__ import annotations

from .types import (
    AssumptionStatus,
    AssumptionType,
    DiscoveryStatus,
    HypothesisCategory,
    HypothesisStatus,
    HypothesisType,
    ConfidenceTier,
    Criticality,
    EvidenceKind,
    Finding,
    MeasurementRegime,
    ObjectiveKind,
    ObservationStatus,
    PredictionStatus,
    Severity,
    ObjectiveStatus,
)
from .ports import EpistemicGraphPort


def validate_tier_constraints(graph: EpistemicGraphPort) -> list[Finding]:
    """Validate confidence tier and measurement regime constraints across predictions.

    Enforces the following rules for each prediction in the graph:

    - ``FULLY_SPECIFIED`` predictions must have exactly zero free parameters.
      Violation severity: CRITICAL.
    - ``CONDITIONAL`` predictions should declare at least one assumption in
      ``conditional_on``. Violation severity: WARNING.
    - For ``MEASURED`` regime, an ``observed`` value is required once the
      prediction reaches an adjudicated status (CONFIRMED, STRESSED, or
      REFUTED). Violation severity: CRITICAL.
    - For ``BOUND_ONLY`` regime, an ``observed_bound`` is required once
      adjudicated. Violation severity: CRITICAL.

    PENDING and NOT_YET_TESTABLE predictions are allowed to omit observed
    values even when a measurement regime is set, supporting the common
    workflow of registering a prediction before observations are recorded.

    Args:
        graph: The epistemic graph to validate.

    Returns:
        list[Finding]: All tier/measurement findings found.
    """
    findings: list[Finding] = []
    for pid, pred in graph.predictions.items():
        if pred.tier == ConfidenceTier.FULLY_SPECIFIED and pred.free_params != 0:
            findings.append(Finding(
                Severity.CRITICAL,
                f"predictions/{pid}",
                f"FULLY_SPECIFIED prediction has {pred.free_params} free params (must be 0)",
            ))
        if pred.tier == ConfidenceTier.CONDITIONAL and not pred.conditional_on and pred.free_params == 0:
            findings.append(Finding(
                Severity.WARNING,
                f"predictions/{pid}",
                "CONDITIONAL prediction has neither 'conditional_on' assumptions "
                "nor free parameters: expected at least one source of conditionality",
            ))

        requires_recorded_evidence = pred.status in {
            PredictionStatus.CONFIRMED,
            PredictionStatus.STRESSED,
            PredictionStatus.REFUTED,
        }

        if (
            requires_recorded_evidence
            and pred.measurement_regime == MeasurementRegime.MEASURED
            and pred.observed is None
        ):
            findings.append(Finding(
                Severity.CRITICAL,
                f"predictions/{pid}",
                "measurement_regime=MEASURED requires an observed value",
            ))
        if (
            requires_recorded_evidence
            and pred.measurement_regime == MeasurementRegime.BOUND_ONLY
            and pred.observed_bound is None
        ):
            findings.append(Finding(
                Severity.CRITICAL,
                f"predictions/{pid}",
                "measurement_regime=BOUND_ONLY requires observed_bound",
            ))
    return findings


def validate_independence_semantics(graph: EpistemicGraphPort) -> list[Finding]:
    """Validate independence group membership consistency and separation completeness.

    Checks two distinct properties:

    1. **Back-reference consistency** (CRITICAL): Every prediction listed in
       a group's ``member_predictions`` must have its ``independence_group``
       field pointing back to that group.

    2. **Pairwise separation completeness** (CRITICAL): Every pair of groups
       that both have at least one member prediction must have a corresponding
       ``PairwiseSeparation`` record. Empty groups (declarations of intent)
       are exempt to avoid registration deadlocks.

    Args:
        graph: The epistemic graph to validate.

    Returns:
        list[Finding]: All independence-related findings found.
    """
    findings: list[Finding] = []

    # Check group membership consistency
    for gid, group in graph.independence_groups.items():
        for pid in group.member_predictions:
            pred = graph.predictions.get(pid)
            if pred is None:
                continue
            if pred.independence_group != gid:
                findings.append(Finding(
                    Severity.CRITICAL,
                    f"independence_groups/{gid}",
                    f"Prediction {pid} listed but doesn't back-reference this group",
                ))

    # Check pairwise separation completeness.
    # A separation is only required once BOTH groups have at least one member
    # prediction. An empty group is a declaration of intent. Requiring a
    # separation before any predictions exist creates an unresolvable
    # registration deadlock (the separation needs both groups, the second
    # group needs the separation to pass validation).
    group_ids = sorted(graph.independence_groups.keys())
    seen_pairs: set[tuple[str, str]] = set()
    for ps in graph.pairwise_separations.values():
        pair = (min(ps.group_a, ps.group_b), max(ps.group_a, ps.group_b))
        seen_pairs.add(pair)

    for i, a in enumerate(group_ids):
        for b in group_ids[i + 1:]:
            if (not graph.independence_groups[a].member_predictions
                    or not graph.independence_groups[b].member_predictions):
                continue
            pair = (min(a, b), max(a, b))
            if pair not in seen_pairs:
                findings.append(Finding(
                    Severity.CRITICAL,
                    "independence_groups/pairwise_separation_basis",
                    f"Missing pairwise separation for ({a}, {b})",
                ))

    return findings


def validate_coverage(graph: EpistemicGraphPort) -> list[Finding]:
    """Check for analysis and prediction coverage gaps across the graph.

    Reports advisory findings for structural blind spots:

    - ``QUANTITATIVE`` hypotheses with no linked analyses (INFO).
    - ``EMPIRICAL`` assumptions with no ``falsifiable_consequence`` (WARNING).
    - Any predictions in ``STRESSED`` status requiring vigilance (WARNING).

    Args:
        graph: The epistemic graph to validate.

    Returns:
        list[Finding]: All coverage findings found.
    """
    findings: list[Finding] = []

    for cid, hypothesis in graph.hypotheses.items():
        if hypothesis.category == HypothesisCategory.QUANTITATIVE and not hypothesis.analyses:
            findings.append(Finding(
                Severity.INFO,
                f"hypotheses/{cid}",
                "Quantitative hypothesis has no linked analyses",
            ))

    for aid, assumption in graph.assumptions.items():
        if assumption.type == AssumptionType.EMPIRICAL and not assumption.falsifiable_consequence:
            findings.append(Finding(
                Severity.WARNING,
                f"assumptions/{aid}",
                "Empirical assumption has no falsifiable consequence",
            ))

    stressed = [
        pid for pid, p in graph.predictions.items()
        if p.status == PredictionStatus.STRESSED
    ]
    if stressed:
        findings.append(Finding(
            Severity.WARNING,
            "predictions",
            f"STRESSED predictions requiring vigilance: {stressed}",
        ))

    return findings


def validate_assumption_testability(graph: EpistemicGraphPort) -> list[Finding]:
    """Flag assumptions with a falsifiable consequence but no testing predictions.

    If an assumption declares a ``falsifiable_consequence`` but has an empty
    ``tested_by`` set, it means the assumption claims to be testable but
    nothing in the graph is actually testing it. Severity: WARNING.

    Args:
        graph: The epistemic graph to validate.

    Returns:
        list[Finding]: One WARNING per untested assumption with a
            falsifiable consequence.
    """
    findings: list[Finding] = []
    for aid, assumption in graph.assumptions.items():
        if assumption.falsifiable_consequence and not assumption.tested_by:
            findings.append(Finding(
                Severity.WARNING,
                f"assumptions/{aid}",
                "Assumption has falsifiable_consequence but no predictions in tested_by",
            ))
    return findings


def validate_retracted_hypothesis_citations(graph: EpistemicGraphPort) -> list[Finding]:
    """Flag predictions or hypotheses that still cite a retracted hypothesis.

    Retracted hypotheses are invalidated assertions that should not be relied
    upon. Active predictions (PENDING, CONFIRMED, STRESSED, NOT_YET_TESTABLE)
    and active hypotheses (ACTIVE, REVISED, DEFERRED) citing a retracted
    hypothesis are CRITICAL. They need remediation. Terminal predictions
    (REFUTED, SUPERSEDED) and terminal hypotheses (RETRACTED) are downgraded
    to INFO since they are historical records requiring no action.

    Args:
        graph: The epistemic graph to validate.

    Returns:
        list[Finding]: One finding per prediction or hypothesis that
            cites a retracted hypothesis.
    """
    findings: list[Finding] = []
    retracted = {
        cid for cid, c in graph.hypotheses.items()
        if c.status == HypothesisStatus.RETRACTED
    }
    if not retracted:
        return findings

    terminal_pred_statuses = {PredictionStatus.REFUTED, PredictionStatus.SUPERSEDED}
    terminal_hyp_statuses = {HypothesisStatus.RETRACTED}

    for pid, pred in graph.predictions.items():
        cited = pred.hypothesis_ids & retracted
        if cited:
            severity = (
                Severity.INFO if pred.status in terminal_pred_statuses
                else Severity.CRITICAL
            )
            findings.append(Finding(
                severity,
                f"predictions/{pid}",
                f"Prediction cites retracted hypothesis(s): {sorted(cited)}",
            ))
    for cid, hypothesis in graph.hypotheses.items():
        bad_deps = hypothesis.depends_on & retracted
        if bad_deps:
            severity = (
                Severity.INFO if hypothesis.status in terminal_hyp_statuses
                else Severity.CRITICAL
            )
            findings.append(Finding(
                severity,
                f"hypotheses/{cid}",
                f"Hypothesis depends on retracted hypothesis(s): {sorted(bad_deps)}",
            ))
    return findings


def validate_implicit_assumption_coverage(graph: EpistemicGraphPort) -> list[Finding]:
    """Flag assumptions that silently underpin predictions but are never tested.

    An assumption is 'silently depended on' if it appears in the implicit
    assumption set of one or more predictions (via hypothesis lineage, depends_on
    chains, or conditional_on) but has no ``tested_by`` coverage and is not
    in the ``tests_assumptions`` of any prediction that depends on it.

    Reports one INFO finding per uncovered assumption, not per prediction.
    This helps researchers identify hidden structural dependencies that
    may represent blind spots in the testing strategy.

    Args:
        graph: The epistemic graph to validate.

    Returns:
        list[Finding]: One INFO finding per uncovered implicit assumption.
    """
    findings: list[Finding] = []

    # Build: for each assumption, which predictions implicitly depend on it
    implicit_dependents: dict = {}
    for pid in graph.predictions:
        for aid in graph.prediction_implicit_assumptions(pid):
            implicit_dependents.setdefault(aid, set()).add(pid)

    for aid, pids in implicit_dependents.items():
        assumption = graph.assumptions.get(aid)
        if assumption is None:
            continue
        # Explicit testers: predictions in the dependent set that list this assumption in tests_assumptions
        explicit_testers = {
            pid for pid in pids
            if aid in graph.predictions[pid].tests_assumptions
        }
        if not assumption.tested_by and not explicit_testers:
            findings.append(Finding(
                Severity.INFO,
                f"assumptions/{aid}",
                f"Assumption implicitly underpins {len(pids)} prediction(s) "
                f"but has no tested_by coverage: {sorted(pids)}",
            ))

    return findings


def validate_tests_conditional_overlap(graph: EpistemicGraphPort) -> list[Finding]:
    """Flag predictions that both test and condition on the same assumption.

    ``tests_assumptions`` means 'this outcome bears on whether the assumption
    holds'. ``conditional_on`` means 'this prediction is only valid if the
    assumption holds'. These are logically contradictory for the same
    assumption. You cannot simultaneously test something you assume to be
    true. Severity: CRITICAL.

    Args:
        graph: The epistemic graph to validate.

    Returns:
        list[Finding]: One CRITICAL finding per prediction with overlap
            between ``tests_assumptions`` and ``conditional_on``.
    """
    findings: list[Finding] = []
    for pid, pred in graph.predictions.items():
        overlap = pred.tests_assumptions & pred.conditional_on
        if overlap:
            findings.append(Finding(
                Severity.CRITICAL,
                f"predictions/{pid}",
                f"Assumption(s) in both tests_assumptions and conditional_on "
                f"(logically contradictory): {sorted(overlap)}",
            ))
    return findings


def validate_foundational_hypothesis_deps(graph: EpistemicGraphPort) -> list[Finding]:
    """Flag foundational hypotheses that have dependencies on other hypotheses.

    Foundational hypotheses are axioms. By definition they should not depend
    on other hypotheses. Having ``depends_on`` entries on a foundational hypothesis
    indicates a misclassification or structural error. Severity: WARNING.

    Args:
        graph: The epistemic graph to validate.

    Returns:
        list[Finding]: One WARNING per foundational hypothesis with non-empty
            ``depends_on``.
    """
    findings: list[Finding] = []
    for cid, hypothesis in graph.hypotheses.items():
        if hypothesis.type == HypothesisType.FOUNDATIONAL and hypothesis.depends_on:
            findings.append(Finding(
                Severity.WARNING,
                f"hypotheses/{cid}",
                f"Foundational hypothesis has depends_on entries "
                f"(foundational hypotheses are axioms): {sorted(hypothesis.depends_on)}",
            ))
    return findings


def validate_evidence_consistency(graph: EpistemicGraphPort) -> list[Finding]:
    """Flag logically inconsistent evidence_kind/tier combinations.

    ``FIT_CHECK`` means the model was tuned/calibrated to match this data.
    The only logically consistent ``EvidenceKind`` for a ``FIT_CHECK`` tier
    is ``FIT_CONSISTENCY``.

    - ``FIT_CHECK`` + ``NOVEL_PREDICTION`` is contradictory: a fit check
      cannot be a novel prediction. Severity: WARNING.
    - ``FIT_CHECK`` + ``RETRODICTION`` is contradictory: retrodiction means
      the data was NOT used to fit parameters, but FIT_CHECK means it was.
      Severity: WARNING.

    Args:
        graph: The epistemic graph to validate.

    Returns:
        list[Finding]: One WARNING per prediction with a contradictory
            FIT_CHECK + evidence_kind combination.
    """
    findings: list[Finding] = []
    for pid, pred in graph.predictions.items():
        if pred.tier == ConfidenceTier.FIT_CHECK:
            if pred.evidence_kind == EvidenceKind.NOVEL_PREDICTION:
                findings.append(Finding(
                    Severity.WARNING,
                    f"predictions/{pid}",
                    "FIT_CHECK prediction marked as NOVEL_PREDICTION: "
                    "fit checks are definitionally not novel predictions",
                ))
            elif pred.evidence_kind == EvidenceKind.RETRODICTION:
                findings.append(Finding(
                    Severity.WARNING,
                    f"predictions/{pid}",
                    "FIT_CHECK prediction marked as RETRODICTION: "
                    "retrodiction means data was not used for fitting, "
                    "which contradicts FIT_CHECK",
                ))
    return findings


def validate_conditional_assumption_pressure(graph: EpistemicGraphPort) -> list[Finding]:
    """Flag confirmed/stressed predictions conditional on assumptions under pressure.

    If prediction P is conditional on assumption A (A in ``P.conditional_on``),
    and some other prediction Q that explicitly tests A (A in
    ``Q.tests_assumptions``) has been REFUTED, then A is under adversarial
    pressure. P's status was established when A was considered sound; that
    basis is now in question.

    Only CONFIRMED and STRESSED predictions are flagged. PENDING predictions
    haven't been confirmed yet (no false sense of security to break), and
    REFUTED predictions are already in a terminal state.

    This does NOT automatically change any prediction's status. It surfaces
    the structural connection so the researcher cannot silently overlook it.
    Severity: WARNING.

    Args:
        graph: The epistemic graph to validate.

    Returns:
        list[Finding]: One WARNING per affected prediction, identifying
            the pressured assumptions and the refuting predictions.
    """
    findings: list[Finding] = []

    # Build: assumption → set of REFUTED predictions that test it
    refuted_tests: dict = {}
    for pid, pred in graph.predictions.items():
        if pred.status == PredictionStatus.REFUTED:
            for aid in pred.tests_assumptions:
                refuted_tests.setdefault(aid, set()).add(pid)

    if not refuted_tests:
        return findings

    active_statuses = {PredictionStatus.CONFIRMED, PredictionStatus.STRESSED}
    for pid, pred in graph.predictions.items():
        if pred.status not in active_statuses:
            continue
        pressured = pred.conditional_on & refuted_tests.keys()
        if not pressured:
            continue
        refuting_preds: set = set()
        for aid in pressured:
            refuting_preds.update(refuted_tests[aid])
        findings.append(Finding(
            Severity.WARNING,
            f"predictions/{pid}",
            f"Prediction {pid} is {pred.status.value} but is conditional on "
            f"assumption(s) {sorted(pressured)} whose tester(s) "
            f"{sorted(refuting_preds)} have been REFUTED. "
            f"The conditional basis of this prediction is now under pressure.",
        ))

    return findings


def validate_stress_criteria(graph: EpistemicGraphPort) -> list[Finding]:
    """Flag STRESSED predictions without explicit stress criteria.

    The boundary between CONFIRMED and STRESSED is philosophically
    ambiguous. Making the researcher declare ``stress_criteria`` upfront
    (what evidence would constitute tension without full refutation)
    ensures the adjudication is explicit and auditable rather than
    ad-hoc. Severity: WARNING.

    Args:
        graph: The epistemic graph to validate.

    Returns:
        list[Finding]: One WARNING per STRESSED prediction missing
            ``stress_criteria``.
    """
    findings: list[Finding] = []
    for pid, pred in graph.predictions.items():
        if pred.status == PredictionStatus.STRESSED and not pred.stress_criteria:
            findings.append(Finding(
                Severity.WARNING,
                f"predictions/{pid}",
                "STRESSED prediction has no stress_criteria: the boundary "
                "between CONFIRMED and STRESSED should be declared explicitly",
            ))
    return findings


def validate_retracted_observation_citations(graph: EpistemicGraphPort) -> list[Finding]:
    """Flag observations that still link to retracted hypotheses or retracted observations linked to predictions.

    If an observation's ``related_hypotheses`` includes hypotheses that have been
    retracted, the observation's interpretation may be compromised.
    Also flags observations in RETRACTED status that are still linked to
    predictions. Active predictions (PENDING, CONFIRMED, STRESSED,
    NOT_YET_TESTABLE) are WARNING; terminal predictions (REFUTED, SUPERSEDED)
    are downgraded to INFO since they are historical records.

    Args:
        graph: The epistemic graph to validate.

    Returns:
        list[Finding]: One finding per problematic observation.
    """
    findings: list[Finding] = []
    retracted_hypotheses = {
        cid for cid, c in graph.hypotheses.items()
        if c.status == HypothesisStatus.RETRACTED
    }
    terminal_pred_statuses = {PredictionStatus.REFUTED, PredictionStatus.SUPERSEDED}
    for oid, obs in graph.observations.items():
        cited = obs.related_hypotheses & retracted_hypotheses
        if cited:
            findings.append(Finding(
                Severity.WARNING,
                f"observations/{oid}",
                f"Observation references retracted hypothesis(s): {sorted(cited)}",
            ))
        if obs.status == ObservationStatus.RETRACTED and obs.predictions:
            active_preds = {
                pid for pid in obs.predictions
                if (p := graph.predictions.get(pid)) is not None
                and p.status not in terminal_pred_statuses
            }
            terminal_preds = obs.predictions - active_preds
            if active_preds:
                findings.append(Finding(
                    Severity.WARNING,
                    f"observations/{oid}",
                    f"Retracted observation still linked to active prediction(s): "
                    f"{sorted(active_preds)}",
                ))
            if terminal_preds:
                findings.append(Finding(
                    Severity.INFO,
                    f"observations/{oid}",
                    f"Retracted observation linked to terminal prediction(s): "
                    f"{sorted(terminal_preds)}",
                ))
    return findings


def validate_objective_abandonment_impact(graph: EpistemicGraphPort) -> list[Finding]:
    """Flag hypotheses whose only theoretical motivation comes from terminal objectives.

    If all objectives referenced by a hypothesis have been abandoned, superseded,
    or declared infeasible, the hypothesis has lost its theoretical motivation.
    This does not invalidate the hypothesis (it may still be empirically
    supported), but the researcher should be aware. Severity: WARNING.

    Args:
        graph: The epistemic graph to validate.

    Returns:
        list[Finding]: One WARNING per hypothesis with only terminal
            theoretical motivation.
    """
    findings: list[Finding] = []
    terminal_statuses = {
        ObjectiveStatus.ABANDONED,
        ObjectiveStatus.SUPERSEDED,
        ObjectiveStatus.INFEASIBLE,
    }
    for cid, hypothesis in graph.hypotheses.items():
        if not hypothesis.objectives:
            continue
        all_terminal = all(
            graph.objectives.get(tid) is not None
            and graph.objectives[tid].status in terminal_statuses
            for tid in hypothesis.objectives
        )
        if all_terminal:
            findings.append(Finding(
                Severity.WARNING,
                f"hypotheses/{cid}",
                f"All motivating objectives are terminal: "
                f"{sorted(hypothesis.objectives)}. Hypothesis has lost theoretical "
                f"motivation.",
            ))
    return findings


def validate_load_bearing_assumption_coverage(graph: EpistemicGraphPort) -> list[Finding]:
    """Flag LOAD_BEARING or HIGH criticality assumptions with no tested_by coverage.

    Load-bearing assumptions are single points of failure. If they have
    no predictions testing them, the project has a critical blind spot.
    Severity: WARNING for HIGH, CRITICAL for LOAD_BEARING.

    Args:
        graph: The epistemic graph to validate.

    Returns:
        list[Finding]: One finding per high-criticality untested assumption.
    """
    findings: list[Finding] = []
    for aid, assumption in graph.assumptions.items():
        if assumption.criticality == Criticality.LOAD_BEARING and not assumption.tested_by:
            findings.append(Finding(
                Severity.CRITICAL,
                f"assumptions/{aid}",
                "LOAD_BEARING assumption has no predictions in tested_by: "
                "this is a single point of failure with no active test",
            ))
        elif assumption.criticality == Criticality.HIGH and not assumption.tested_by:
            findings.append(Finding(
                Severity.WARNING,
                f"assumptions/{aid}",
                "HIGH criticality assumption has no predictions in tested_by",
            ))
    return findings


def validate_testability_regime_consistency(graph: EpistemicGraphPort) -> list[Finding]:
    """Flag NOT_YET_TESTABLE predictions whose measurement regime contradicts their status.

    A ``NOT_YET_TESTABLE`` prediction that declares ``MEASURED`` or
    ``BOUND_ONLY`` regime is contradictory. The regime claims evidence
    form is known, but the status says no feasible test exists.
    ``UNMEASURED`` is the expected regime for ``NOT_YET_TESTABLE``.
    Severity: WARNING.

    Args:
        graph: The epistemic graph to validate.

    Returns:
        list[Finding]: One WARNING per inconsistent prediction.
    """
    findings: list[Finding] = []
    for pid, pred in graph.predictions.items():
        if (
            pred.status == PredictionStatus.NOT_YET_TESTABLE
            and pred.measurement_regime != MeasurementRegime.UNMEASURED
        ):
            findings.append(Finding(
                Severity.WARNING,
                f"predictions/{pid}",
                f"NOT_YET_TESTABLE prediction has measurement_regime="
                f"{pred.measurement_regime.value}: expected UNMEASURED",
            ))
    return findings


def validate_goal_objective_criteria(graph: EpistemicGraphPort) -> list[Finding]:
    """Flag GOAL objectives without success criteria.

    GOAL objectives represent concrete target outcomes. Without
    ``success_criteria``, there is no way to determine when the
    objective has been achieved. Severity: WARNING.

    Args:
        graph: The epistemic graph to validate.

    Returns:
        list[Finding]: One WARNING per GOAL objective missing
            ``success_criteria``.
    """
    findings: list[Finding] = []
    for oid, obj in graph.objectives.items():
        if obj.kind == ObjectiveKind.GOAL and not obj.success_criteria:
            findings.append(Finding(
                Severity.WARNING,
                f"objectives/{oid}",
                "GOAL objective has no success_criteria: "
                "there is no way to determine when this objective is achieved",
            ))
    return findings


def validate_supersession_chains(graph: EpistemicGraphPort) -> list[Finding]:
    """Validate supersession provenance chains across hypotheses, predictions, and objectives.

    Checks four properties:

    1. **Dangling superseded_by on Hypothesis** (CRITICAL): If set, the
       referenced hypothesis must exist in the graph.
    2. **Missing superseded_by on revised/retracted Hypothesis** (WARNING):
       A REVISED or RETRACTED hypothesis should declare what replaced it to
       maintain a complete provenance chain.
    3. **Dangling superseded_by on Objective** (CRITICAL): If set, the
       referenced objective must exist.
    4. **Missing superseded_by on superseded Objective** (WARNING): A
       SUPERSEDED objective should declare its successor.
    5. **Dangling supersedes on Prediction** (CRITICAL): If set, the
       referenced predecessor prediction must exist.

    Args:
        graph: The epistemic graph to validate.

    Returns:
        list[Finding]: All supersession-chain findings found.
    """
    findings: list[Finding] = []

    # Hypotheses
    for hid, hyp in graph.hypotheses.items():
        if hyp.superseded_by is not None and hyp.superseded_by not in graph.hypotheses:
            findings.append(Finding(
                Severity.CRITICAL,
                f"hypotheses/{hid}",
                f"superseded_by references non-existent hypothesis: {hyp.superseded_by}",
            ))
        if hyp.status == HypothesisStatus.REVISED and hyp.superseded_by is None:
            findings.append(Finding(
                Severity.WARNING,
                f"hypotheses/{hid}",
                "REVISED hypothesis has no superseded_by: "
                "provenance chain is incomplete",
            ))

    # Objectives
    for oid, obj in graph.objectives.items():
        if obj.superseded_by is not None and obj.superseded_by not in graph.objectives:
            findings.append(Finding(
                Severity.CRITICAL,
                f"objectives/{oid}",
                f"superseded_by references non-existent objective: {obj.superseded_by}",
            ))
        if obj.status == ObjectiveStatus.SUPERSEDED and obj.superseded_by is None:
            findings.append(Finding(
                Severity.WARNING,
                f"objectives/{oid}",
                "SUPERSEDED objective has no superseded_by: "
                "provenance chain is incomplete",
            ))

    # Predictions
    for pid, pred in graph.predictions.items():
        if pred.supersedes is not None and pred.supersedes not in graph.predictions:
            findings.append(Finding(
                Severity.CRITICAL,
                f"predictions/{pid}",
                f"supersedes references non-existent prediction: {pred.supersedes}",
            ))

    return findings


def validate_compromised_observation_basis(graph: EpistemicGraphPort) -> list[Finding]:
    """Flag active predictions whose supporting observations are disputed or retracted.

    If a CONFIRMED or STRESSED prediction has observations that have been
    DISPUTED or RETRACTED, the empirical basis for the adjudication is
    compromised. The researcher should review whether the prediction's
    status is still warranted.

    Only active adjudicated predictions (CONFIRMED, STRESSED) are flagged .
    PENDING predictions haven't been adjudicated yet, and terminal predictions
    (REFUTED, SUPERSEDED) are historical records. Severity: WARNING.

    Args:
        graph: The epistemic graph to validate.

    Returns:
        list[Finding]: One WARNING per affected prediction, identifying
            the compromised observations.
    """
    findings: list[Finding] = []
    active_adjudicated = {PredictionStatus.CONFIRMED, PredictionStatus.STRESSED}
    compromised_statuses = {ObservationStatus.DISPUTED, ObservationStatus.RETRACTED}

    for pid, pred in graph.predictions.items():
        if pred.status not in active_adjudicated:
            continue
        bad_obs = {
            oid for oid in pred.observations
            if (obs := graph.observations.get(oid)) is not None
            and obs.status in compromised_statuses
        }
        if bad_obs:
            findings.append(Finding(
                Severity.WARNING,
                f"predictions/{pid}",
                f"{pred.status.value} prediction has disputed/retracted "
                f"observation(s): {sorted(bad_obs)}: adjudication basis "
                f"may be compromised",
            ))
    return findings


def validate_supersession_status_consistency(graph: EpistemicGraphPort) -> list[Finding]:
    """Flag predictions with inconsistent supersession link/status pairing.

    Two checks:

    1. If prediction B has ``supersedes = A``, then A's status should be
       ``SUPERSEDED``. If A is still active, the supersession is incomplete.
       Severity: WARNING.
    2. If a prediction has status ``SUPERSEDED`` but no other prediction in
       the graph has ``supersedes`` pointing to it, the successor is missing.
       Severity: WARNING.

    Args:
        graph: The epistemic graph to validate.

    Returns:
        list[Finding]: All supersession-status findings found.
    """
    findings: list[Finding] = []

    # Build reverse map: predecessor_id → set of successor_ids
    superseded_by_map: dict[str, set[str]] = {}
    for pid, pred in graph.predictions.items():
        if pred.supersedes is not None:
            superseded_by_map.setdefault(pred.supersedes, set()).add(pid)
            # Check 1: predecessor should be SUPERSEDED
            predecessor = graph.predictions.get(pred.supersedes)
            if predecessor is not None and predecessor.status != PredictionStatus.SUPERSEDED:
                findings.append(Finding(
                    Severity.WARNING,
                    f"predictions/{pred.supersedes}",
                    f"Prediction is superseded by {pid} but status is "
                    f"{predecessor.status.value}, not SUPERSEDED",
                ))

    # Check 2: SUPERSEDED predictions should have a successor
    for pid, pred in graph.predictions.items():
        if pred.status == PredictionStatus.SUPERSEDED and pid not in superseded_by_map:
            findings.append(Finding(
                Severity.WARNING,
                f"predictions/{pid}",
                "SUPERSEDED prediction has no successor: "
                "no other prediction declares supersedes pointing to it",
            ))

    return findings


def validate_refutation_criteria(graph: EpistemicGraphPort) -> list[Finding]:
    """Flag REFUTED predictions without explicit refutation criteria.

    If a prediction has been adjudicated as REFUTED but never declared
    ``refutation_criteria``, the refutation is ad-hoc and unauditable.
    The criteria should make it clear what evidence threshold was crossed.
    Severity: WARNING.

    Args:
        graph: The epistemic graph to validate.

    Returns:
        list[Finding]: One WARNING per REFUTED prediction missing
            ``refutation_criteria``.
    """
    findings: list[Finding] = []
    for pid, pred in graph.predictions.items():
        if pred.status == PredictionStatus.REFUTED and not pred.refutation_criteria:
            findings.append(Finding(
                Severity.WARNING,
                f"predictions/{pid}",
                "REFUTED prediction has no refutation_criteria: the basis "
                "for refutation should be declared explicitly for auditability",
            ))
    return findings


def validate_observed_but_pending(graph: EpistemicGraphPort) -> list[Finding]:
    """Flag predictions with recorded evidence that have not been adjudicated.

    If a prediction has ``observed`` or ``observed_bound`` set but status
    is still ``PENDING``, evidence has been recorded but the researcher
    has not yet adjudicated. This is a workflow completeness nudge, not
    an error. Severity: INFO.

    Args:
        graph: The epistemic graph to validate.

    Returns:
        list[Finding]: One INFO per prediction with evidence but PENDING
            status.
    """
    findings: list[Finding] = []
    for pid, pred in graph.predictions.items():
        if pred.status != PredictionStatus.PENDING:
            continue
        has_evidence = pred.observed is not None or pred.observed_bound is not None
        if has_evidence:
            findings.append(Finding(
                Severity.INFO,
                f"predictions/{pid}",
                "Prediction has recorded observed data but status is still "
                "PENDING: evidence may be ready for adjudication",
            ))
    return findings


def validate_deferred_hypothesis_active_predictions(graph: EpistemicGraphPort) -> list[Finding]:
    """Flag DEFERRED hypotheses that still have active predictions.

    If a hypothesis has status ``DEFERRED`` (investigation paused) but
    predictions derived from it are still ``PENDING``, ``CONFIRMED``, or
    ``STRESSED``, those predictions are in limbo. Their theoretical basis
    is on hold but they are being treated as active. Severity: WARNING.

    Args:
        graph: The epistemic graph to validate.

    Returns:
        list[Finding]: One WARNING per DEFERRED hypothesis with active
            predictions.
    """
    findings: list[Finding] = []
    active_pred_statuses = {
        PredictionStatus.PENDING,
        PredictionStatus.CONFIRMED,
        PredictionStatus.STRESSED,
    }
    deferred = {
        cid for cid, c in graph.hypotheses.items()
        if c.status == HypothesisStatus.DEFERRED
    }
    if not deferred:
        return findings

    # Build: hypothesis → active predictions derived from it
    for cid in deferred:
        active_preds = [
            pid for pid, pred in graph.predictions.items()
            if cid in pred.hypothesis_ids and pred.status in active_pred_statuses
        ]
        if active_preds:
            findings.append(Finding(
                Severity.WARNING,
                f"hypotheses/{cid}",
                f"DEFERRED hypothesis still has active prediction(s): "
                f"{sorted(active_preds)}: their theoretical basis is on hold",
            ))
    return findings


def validate_orphaned_predictions(graph: EpistemicGraphPort) -> list[Finding]:
    """Flag predictions with no hypothesis derivation chain.

    A prediction with empty ``hypothesis_ids`` has no logical root. It
    is an assertion without a derivation chain. This is common during
    early exploratory work but should be resolved as the graph matures.
    Severity: INFO.

    Args:
        graph: The epistemic graph to validate.

    Returns:
        list[Finding]: One INFO per prediction with empty ``hypothesis_ids``.
    """
    findings: list[Finding] = []
    for pid, pred in graph.predictions.items():
        if not pred.hypothesis_ids:
            findings.append(Finding(
                Severity.INFO,
                f"predictions/{pid}",
                "Prediction has no hypothesis_ids: no derivation chain "
                "connects it to the reasoning graph",
            ))
    return findings


def validate_prediction_transition(
    graph: EpistemicGraphPort,
    pid: str,
    new_status: PredictionStatus,
) -> list[Finding]:
    """Validate semantic concerns for a proposed prediction status transition.

    Returns warnings for transitions that are technically valid but may
    indicate incomplete researcher intent. Hard blocks (logically
    impossible transitions) are enforced by graph mutation guards in
    ``graph.py``. This function only surfaces advisory findings.

    Designed for composition: the gateway ``_finalize_mutation`` can call
    this post-transition, or a researcher can call it directly before
    committing a transition.

    Checks:
        - Transitioning to STRESSED without ``stress_criteria`` defined.
        - Transitioning to REFUTED without ``refutation_criteria`` defined.
        - Transitioning to NOT_YET_TESTABLE with a non-UNMEASURED
          ``measurement_regime``.

    Args:
        graph: The epistemic graph containing the prediction.
        pid: The prediction ID being transitioned.
        new_status: The proposed new status.

    Returns:
        list[Finding]: Transition-specific warnings (never CRITICAL).
    """
    findings: list[Finding] = []
    pred = graph.predictions.get(pid)
    if pred is None:
        return findings

    if new_status == PredictionStatus.STRESSED and not pred.stress_criteria:
        findings.append(Finding(
            Severity.WARNING,
            f"predictions/{pid}",
            "Transitioning to STRESSED without stress_criteria: "
            "consider documenting what evidence threshold separates "
            "STRESSED from REFUTED",
        ))
    if new_status == PredictionStatus.REFUTED and not pred.refutation_criteria:
        findings.append(Finding(
            Severity.WARNING,
            f"predictions/{pid}",
            "Transitioning to REFUTED without refutation_criteria: "
            "consider documenting what evidence constituted decisive "
            "refutation",
        ))
    if (
        new_status == PredictionStatus.NOT_YET_TESTABLE
        and pred.measurement_regime != MeasurementRegime.UNMEASURED
    ):
        findings.append(Finding(
            Severity.WARNING,
            f"predictions/{pid}",
            f"Transitioning to NOT_YET_TESTABLE but measurement_regime "
            f"is {pred.measurement_regime.value}: consider whether "
            f"UNMEASURED is more appropriate",
        ))
    return findings


def validate_falsified_assumption_impact(graph: EpistemicGraphPort) -> list[Finding]:
    """Flag active entities that depend on FALSIFIED or QUESTIONED assumptions.

    When an assumption's status is FALSIFIED, all entities that depend on it
    need re-evaluation:

    - Active hypotheses whose ``assumptions`` set includes the assumption.
      FALSIFIED → CRITICAL; QUESTIONED → WARNING.
    - Active predictions whose ``conditional_on`` includes the assumption.
      FALSIFIED → CRITICAL; QUESTIONED → WARNING.

    Terminal entities (RETRACTED hypotheses, REFUTED/SUPERSEDED predictions)
    are excluded. They are historical records.

    This complements ``validate_conditional_assumption_pressure`` (which checks
    if *testing predictions* have been REFUTED) by directly inspecting the
    assumption's own lifecycle status.

    Args:
        graph: The epistemic graph to validate.

    Returns:
        list[Finding]: One finding per affected entity.
    """
    findings: list[Finding] = []
    compromised = {
        aid: assumption
        for aid, assumption in graph.assumptions.items()
        if assumption.status in {AssumptionStatus.FALSIFIED, AssumptionStatus.QUESTIONED}
    }
    if not compromised:
        return findings

    active_hyp_statuses = {HypothesisStatus.ACTIVE, HypothesisStatus.REVISED, HypothesisStatus.DEFERRED}
    active_pred_statuses = {
        PredictionStatus.PENDING,
        PredictionStatus.CONFIRMED,
        PredictionStatus.STRESSED,
        PredictionStatus.NOT_YET_TESTABLE,
    }

    for aid, assumption in compromised.items():
        severity = (
            Severity.CRITICAL if assumption.status == AssumptionStatus.FALSIFIED
            else Severity.WARNING
        )

        # Hypotheses referencing this assumption
        for cid, hyp in graph.hypotheses.items():
            if aid in hyp.assumptions and hyp.status in active_hyp_statuses:
                findings.append(Finding(
                    severity,
                    f"hypotheses/{cid}",
                    f"Hypothesis references {assumption.status.value} assumption "
                    f"{aid}: re-evaluation needed",
                ))

        # Predictions conditional on this assumption
        for pid, pred in graph.predictions.items():
            if aid in pred.conditional_on and pred.status in active_pred_statuses:
                findings.append(Finding(
                    severity,
                    f"predictions/{pid}",
                    f"Prediction is conditional on {assumption.status.value} "
                    f"assumption {aid}: validity basis compromised",
                ))

    return findings


def validate_adjudication_has_observations(graph: EpistemicGraphPort) -> list[Finding]:
    """Flag adjudicated predictions with no linked observations.

    When a prediction is CONFIRMED, STRESSED, or REFUTED, its adjudication
    should be grounded in empirical evidence linked via the ``observations``
    set. A prediction adjudicated without any observation links has an
    unauditable empirical basis.

    UNMEASURED regime predictions are exempt. They have no direct
    measurement path by definition.

    Severity: WARNING.

    Args:
        graph: The epistemic graph to validate.

    Returns:
        list[Finding]: One WARNING per adjudicated prediction with empty
            ``observations``.
    """
    findings: list[Finding] = []
    adjudicated = {PredictionStatus.CONFIRMED, PredictionStatus.STRESSED, PredictionStatus.REFUTED}
    for pid, pred in graph.predictions.items():
        if (
            pred.status in adjudicated
            and pred.measurement_regime != MeasurementRegime.UNMEASURED
            and not pred.observations
        ):
            findings.append(Finding(
                Severity.WARNING,
                f"predictions/{pid}",
                f"{pred.status.value} prediction has no linked observations: "
                f"adjudication should be grounded in empirical evidence",
            ))
    return findings


def validate_adjudication_rationale(graph: EpistemicGraphPort) -> list[Finding]:
    """Flag adjudicated predictions without an adjudication rationale.

    When a prediction is CONFIRMED, STRESSED, or REFUTED, the researcher
    should document *why*. What evidence was decisive and how it maps to
    the adjudication thresholds. Without ``adjudication_rationale``, the
    decision is unauditable.

    Completes the adjudication documentation triad alongside
    ``validate_stress_criteria`` and ``validate_refutation_criteria``.

    Severity: WARNING.

    Args:
        graph: The epistemic graph to validate.

    Returns:
        list[Finding]: One WARNING per adjudicated prediction missing
            ``adjudication_rationale``.
    """
    findings: list[Finding] = []
    adjudicated = {PredictionStatus.CONFIRMED, PredictionStatus.STRESSED, PredictionStatus.REFUTED}
    for pid, pred in graph.predictions.items():
        if pred.status in adjudicated and not pred.adjudication_rationale:
            findings.append(Finding(
                Severity.WARNING,
                f"predictions/{pid}",
                f"{pred.status.value} prediction has no adjudication_rationale: "
                f"document the evidence and reasoning behind the adjudication",
            ))
    return findings


def validate_hypothesis_refutation_criteria(graph: EpistemicGraphPort) -> list[Finding]:
    """Flag active hypotheses with predictions but no refutation criteria.

    Popper's falsifiability principle requires that a hypothesis declare
    what would refute it. During early-stage exploration, ``refutation_criteria``
    is optional. But once a hypothesis has predictions testing its
    consequences, it is mature enough that the researcher should have
    articulated what evidence would constitute refutation.

    Only ACTIVE hypotheses with at least one prediction in their derivation
    chain are flagged. Severity: INFO.

    Args:
        graph: The epistemic graph to validate.

    Returns:
        list[Finding]: One INFO per mature hypothesis missing
            ``refutation_criteria``.
    """
    findings: list[Finding] = []
    # Build reverse index: hypothesis → predictions derived from it
    hyp_has_predictions: set = set()
    for pred in graph.predictions.values():
        hyp_has_predictions.update(pred.hypothesis_ids)

    for cid, hyp in graph.hypotheses.items():
        if (
            hyp.status == HypothesisStatus.ACTIVE
            and cid in hyp_has_predictions
            and not hyp.refutation_criteria
        ):
            findings.append(Finding(
                Severity.INFO,
                f"hypotheses/{cid}",
                "Active hypothesis with predictions but no refutation_criteria: "
                "consider documenting what evidence would refute this hypothesis",
            ))
    return findings


def validate_discovery_integration_consistency(graph: EpistemicGraphPort) -> list[Finding]:
    """Flag INTEGRATED discoveries with no structural links to the graph.

    A discovery with status ``INTEGRATED`` claims it has been incorporated
    into hypotheses or predictions. If both ``related_hypotheses`` and
    ``related_predictions`` are empty, the claim is unsubstantiated. The
    researcher should either add links or revert the status to ``NEW``.

    Severity: WARNING.

    Args:
        graph: The epistemic graph to validate.

    Returns:
        list[Finding]: One WARNING per INTEGRATED discovery with no links.
    """
    findings: list[Finding] = []
    for did, disc in graph.discoveries.items():
        if (
            disc.status == DiscoveryStatus.INTEGRATED
            and not disc.related_hypotheses
            and not disc.related_predictions
        ):
            findings.append(Finding(
                Severity.WARNING,
                f"discoveries/{did}",
                "INTEGRATED discovery has no related_hypotheses or "
                "related_predictions: integration claim is unsubstantiated",
            ))
    return findings


def validate_supersession_cycles(graph: EpistemicGraphPort) -> list[Finding]:
    """Detect cycles in supersession chains across predictions, hypotheses, and objectives.

    Supersession is inherently a DAG: "A was replaced by B which was
    replaced by C" forms a linear provenance chain. A cycle
    (A → B → A) is incoherent and indicates a data entry error.

    Checks three independent chains:

    1. Prediction ``supersedes`` chains.
    2. Hypothesis ``superseded_by`` chains.
    3. Objective ``superseded_by`` chains.

    Severity: CRITICAL.

    Args:
        graph: The epistemic graph to validate.

    Returns:
        list[Finding]: One CRITICAL finding per entity involved in a
            supersession cycle.
    """
    findings: list[Finding] = []

    # Prediction supersedes chains (forward: new → old)
    for pid in graph.predictions:
        visited: set[str] = set()
        current = pid
        while current is not None:
            if current in visited:
                findings.append(Finding(
                    Severity.CRITICAL,
                    f"predictions/{pid}",
                    f"Prediction supersession chain starting at {pid} "
                    f"contains a cycle (reached {current} twice)",
                ))
                break
            visited.add(current)
            pred = graph.predictions.get(current)
            current = pred.supersedes if pred is not None else None

    # Hypothesis superseded_by chains (forward: old → new)
    for hid in graph.hypotheses:
        visited = set()
        current = hid
        while current is not None:
            if current in visited:
                findings.append(Finding(
                    Severity.CRITICAL,
                    f"hypotheses/{hid}",
                    f"Hypothesis supersession chain starting at {hid} "
                    f"contains a cycle (reached {current} twice)",
                ))
                break
            visited.add(current)
            hyp = graph.hypotheses.get(current)
            current = hyp.superseded_by if hyp is not None else None

    # Objective superseded_by chains (forward: old → new)
    for oid in graph.objectives:
        visited = set()
        current = oid
        while current is not None:
            if current in visited:
                findings.append(Finding(
                    Severity.CRITICAL,
                    f"objectives/{oid}",
                    f"Objective supersession chain starting at {oid} "
                    f"contains a cycle (reached {current} twice)",
                ))
                break
            visited.add(current)
            obj = graph.objectives.get(current)
            current = obj.superseded_by if obj is not None else None

    return findings


def validate_hypothesis_empirical_interface(graph: EpistemicGraphPort) -> list[Finding]:
    """Flag active hypotheses with no predictions in the graph.

    Popper's falsifiability principle: a scientific hypothesis must
    generate testable predictions. An ACTIVE hypothesis with zero
    predictions citing it anywhere in the graph has no empirical
    interface. It cannot be confirmed, stressed, or refuted.

    This is expected during early-stage development. But as the graph
    matures, hypotheses without predictions represent blind spots in
    the testing strategy.

    Only ACTIVE hypotheses are flagged. DEFERRED, REVISED, and
    RETRACTED hypotheses have other lifecycle semantics.

    Severity: INFO.

    Args:
        graph: The epistemic graph to validate.

    Returns:
        list[Finding]: One INFO per active hypothesis with no predictions.
    """
    findings: list[Finding] = []
    # Build reverse index: hypotheses that have at least one prediction
    hyp_has_predictions: set[str] = set()
    for pred in graph.predictions.values():
        hyp_has_predictions.update(pred.hypothesis_ids)

    for cid, hyp in graph.hypotheses.items():
        if hyp.status == HypothesisStatus.ACTIVE and cid not in hyp_has_predictions:
            findings.append(Finding(
                Severity.INFO,
                f"hypotheses/{cid}",
                "Active hypothesis has no predictions: no empirical "
                "interface exists to test or refute it",
            ))
    return findings


def validate_disconnected_dead_ends(graph: EpistemicGraphPort) -> list[Finding]:
    """Flag dead ends with no structural links to the reasoning graph.

    A dead end records what was tried and why it failed. Without links
    to ``related_hypotheses`` or ``related_predictions``, the dead end
    is a free-floating note disconnected from the research context.
    Linking it to the hypotheses or predictions that failed improves
    navigability and prevents future researchers from repeating the
    same approaches.

    Severity: INFO.

    Args:
        graph: The epistemic graph to validate.

    Returns:
        list[Finding]: One INFO per dead end with no structural links.
    """
    findings: list[Finding] = []
    for did, de in graph.dead_ends.items():
        if not de.related_hypotheses and not de.related_predictions:
            findings.append(Finding(
                Severity.INFO,
                f"dead_ends/{did}",
                "Dead end has no related_hypotheses or related_predictions: "
                "consider linking it to the reasoning it emerged from",
            ))
    return findings


def validate_all(graph: EpistemicGraphPort) -> list[Finding]:
    """Run all domain invariant validators and return the combined findings.

    Executes every semantic/coverage validator in a fixed order and
    concatenates their results. Structural invariants (refs exist, no
    cycles, bidirectional links) are enforced at mutation time in
    ``graph.py``; this function covers the on-demand semantic checks.

    Validator execution order:
        1. Retracted hypothesis citations
        2. Tests/conditional overlap
        3. Tier constraints
        4. Evidence consistency
        5. Independence semantics
        6. Coverage gaps
        7. Assumption testability
        8. Implicit assumption coverage
        9. Foundational hypothesis dependencies
        10. Conditional assumption pressure
        11. Stress criteria
        12. Retracted observation citations
        13. Objective abandonment impact
        14. Load-bearing assumption coverage
        15. Supersession chains
        16. Testability/regime consistency
        17. Goal objective criteria
        18. Compromised observation basis
        19. Supersession status consistency
        20. Refutation criteria
        21. Observed but pending
        22. Deferred hypothesis active predictions
        23. Orphaned predictions
        24. Falsified assumption impact
        25. Adjudication has observations
        26. Adjudication rationale
        27. Hypothesis refutation criteria
        28. Discovery integration consistency
        29. Supersession cycles
        30. Hypothesis empirical interface
        31. Disconnected dead ends

    Args:
        graph: The epistemic graph to validate.

    Returns:
        list[Finding]: All findings from all validators, concatenated
            in execution order.
    """
    return (
        validate_retracted_hypothesis_citations(graph)
        + validate_tests_conditional_overlap(graph)
        + validate_tier_constraints(graph)
        + validate_evidence_consistency(graph)
        + validate_independence_semantics(graph)
        + validate_coverage(graph)
        + validate_assumption_testability(graph)
        + validate_implicit_assumption_coverage(graph)
        + validate_foundational_hypothesis_deps(graph)
        + validate_conditional_assumption_pressure(graph)
        + validate_stress_criteria(graph)
        + validate_retracted_observation_citations(graph)
        + validate_objective_abandonment_impact(graph)
        + validate_load_bearing_assumption_coverage(graph)
        + validate_supersession_chains(graph)
        + validate_testability_regime_consistency(graph)
        + validate_goal_objective_criteria(graph)
        + validate_compromised_observation_basis(graph)
        + validate_supersession_status_consistency(graph)
        + validate_refutation_criteria(graph)
        + validate_observed_but_pending(graph)
        + validate_deferred_hypothesis_active_predictions(graph)
        + validate_orphaned_predictions(graph)
        + validate_falsified_assumption_impact(graph)
        + validate_adjudication_has_observations(graph)
        + validate_adjudication_rationale(graph)
        + validate_hypothesis_refutation_criteria(graph)
        + validate_discovery_integration_consistency(graph)
        + validate_supersession_cycles(graph)
        + validate_hypothesis_empirical_interface(graph)
        + validate_disconnected_dead_ends(graph)
    )
