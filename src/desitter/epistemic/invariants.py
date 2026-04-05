"""Validation rules that span multiple entities.

These require looking at the web as a whole. Each function is pure:
(EpistemicWeb) -> list[Finding].

Structural invariants (refs exist, no cycles, bidirectional links) live
in web.py and are enforced at mutation time.

Semantic/coverage invariants live here and are checked on demand.
"""
from __future__ import annotations

from .types import (
    AssumptionType,
    ClaimCategory,
    ClaimStatus,
    ClaimType,
    ConfidenceTier,
    EvidenceKind,
    Finding,
    MeasurementRegime,
    PredictionStatus,
    Severity,
)
from .web import EpistemicWeb


def validate_tier_constraints(web: EpistemicWeb) -> list[Finding]:
    """FULLY_SPECIFIED: 0 free params. CONDITIONAL: must state conditional_on."""
    findings: list[Finding] = []
    for pid, pred in web.predictions.items():
        if pred.tier == ConfidenceTier.FULLY_SPECIFIED and pred.free_params != 0:
            findings.append(Finding(
                Severity.CRITICAL,
                f"predictions/{pid}",
                f"FULLY_SPECIFIED prediction has {pred.free_params} free params (must be 0)",
            ))
        if pred.tier == ConfidenceTier.CONDITIONAL and not pred.conditional_on:
            findings.append(Finding(
                Severity.WARNING,
                f"predictions/{pid}",
                "CONDITIONAL prediction missing 'conditional_on'",
            ))
        if pred.measurement_regime == MeasurementRegime.MEASURED and pred.observed is None:
            findings.append(Finding(
                Severity.CRITICAL,
                f"predictions/{pid}",
                "measurement_regime=MEASURED requires an observed value",
            ))
        if pred.measurement_regime == MeasurementRegime.BOUND_ONLY and pred.observed_bound is None:
            findings.append(Finding(
                Severity.CRITICAL,
                f"predictions/{pid}",
                "measurement_regime=BOUND_ONLY requires observed_bound",
            ))
    return findings


def validate_independence_semantics(web: EpistemicWeb) -> list[Finding]:
    """Groups must have consistent back-refs. Every pair needs separation basis."""
    findings: list[Finding] = []

    # Check group membership consistency
    for gid, group in web.independence_groups.items():
        for pid in group.member_predictions:
            pred = web.predictions.get(pid)
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
    # prediction. An empty group is a declaration of intent — requiring a
    # separation before any predictions exist creates an unresolvable
    # registration deadlock (the separation needs both groups, the second
    # group needs the separation to pass validation).
    group_ids = sorted(web.independence_groups.keys())
    seen_pairs: set[tuple[str, str]] = set()
    for ps in web.pairwise_separations.values():
        pair = (min(ps.group_a, ps.group_b), max(ps.group_a, ps.group_b))
        seen_pairs.add(pair)

    for i, a in enumerate(group_ids):
        for b in group_ids[i + 1:]:
            if (not web.independence_groups[a].member_predictions
                    or not web.independence_groups[b].member_predictions):
                continue
            pair = (min(a, b), max(a, b))
            if pair not in seen_pairs:
                findings.append(Finding(
                    Severity.CRITICAL,
                    "independence_groups/pairwise_separation_basis",
                    f"Missing pairwise separation for ({a}, {b})",
                ))

    return findings


def validate_coverage(web: EpistemicWeb) -> list[Finding]:
    """Check for analysis and prediction coverage gaps."""
    findings: list[Finding] = []

    for cid, claim in web.claims.items():
        if claim.category == ClaimCategory.NUMERICAL and not claim.analyses:
            findings.append(Finding(
                Severity.INFO,
                f"claims/{cid}",
                "Numerical claim has no linked analyses",
            ))

    for aid, assumption in web.assumptions.items():
        if assumption.type == AssumptionType.EMPIRICAL and not assumption.falsifiable_consequence:
            findings.append(Finding(
                Severity.WARNING,
                f"assumptions/{aid}",
                "Empirical [E] assumption has no falsifiable consequence",
            ))

    stressed = [
        pid for pid, p in web.predictions.items()
        if p.status == PredictionStatus.STRESSED
    ]
    if stressed:
        findings.append(Finding(
            Severity.WARNING,
            "predictions",
            f"STRESSED predictions requiring vigilance: {stressed}",
        ))

    return findings


def validate_assumption_testability(web: EpistemicWeb) -> list[Finding]:
    """Assumptions with a falsifiable consequence should have predictions testing them."""
    findings: list[Finding] = []
    for aid, assumption in web.assumptions.items():
        if assumption.falsifiable_consequence and not assumption.tested_by:
            findings.append(Finding(
                Severity.WARNING,
                f"assumptions/{aid}",
                "Assumption has falsifiable_consequence but no predictions in tested_by",
            ))
    return findings


def validate_retracted_claim_citations(web: EpistemicWeb) -> list[Finding]:
    """CRITICAL: any prediction or claim that still cites a retracted claim."""
    findings: list[Finding] = []
    retracted = {
        cid for cid, c in web.claims.items()
        if c.status == ClaimStatus.RETRACTED
    }
    if not retracted:
        return findings
    for pid, pred in web.predictions.items():
        cited = pred.claim_ids & retracted
        if cited:
            findings.append(Finding(
                Severity.CRITICAL,
                f"predictions/{pid}",
                f"Prediction cites retracted claim(s): {sorted(cited)}",
            ))
    for cid, claim in web.claims.items():
        bad_deps = claim.depends_on & retracted
        if bad_deps:
            findings.append(Finding(
                Severity.CRITICAL,
                f"claims/{cid}",
                f"Claim depends on retracted claim(s): {sorted(bad_deps)}",
            ))
    return findings


def validate_implicit_assumption_coverage(web: EpistemicWeb) -> list[Finding]:
    """Flag assumptions that silently underpin predictions but are never tested.

    An assumption is 'silently depended on' if it appears in the implicit
    assumption set of one or more predictions (via claim lineage, depends_on
    chains, or conditional_on) but has no tested_by coverage and is not in
    the tests_assumptions of any prediction that depends on it.

    Reports one finding per uncovered assumption, not per prediction.
    """
    findings: list[Finding] = []

    # Build: for each assumption, which predictions implicitly depend on it
    implicit_dependents: dict = {}
    for pid in web.predictions:
        for aid in web.prediction_implicit_assumptions(pid):
            implicit_dependents.setdefault(aid, set()).add(pid)

    for aid, pids in implicit_dependents.items():
        assumption = web.assumptions.get(aid)
        if assumption is None:
            continue
        # Explicit testers: predictions in the dependent set that list this assumption in tests_assumptions
        explicit_testers = {
            pid for pid in pids
            if aid in web.predictions[pid].tests_assumptions
        }
        if not assumption.tested_by and not explicit_testers:
            findings.append(Finding(
                Severity.INFO,
                f"assumptions/{aid}",
                f"Assumption implicitly underpins {len(pids)} prediction(s) "
                f"but has no tested_by coverage: {sorted(pids)}",
            ))

    return findings


def validate_tests_conditional_overlap(web: EpistemicWeb) -> list[Finding]:
    """CRITICAL: a prediction cannot both test and condition on the same assumption.

    tests_assumptions means 'this outcome bears on whether the assumption holds'.
    conditional_on means 'this prediction is only valid if the assumption holds'.
    These are logically contradictory for the same assumption.
    """
    findings: list[Finding] = []
    for pid, pred in web.predictions.items():
        overlap = pred.tests_assumptions & pred.conditional_on
        if overlap:
            findings.append(Finding(
                Severity.CRITICAL,
                f"predictions/{pid}",
                f"Assumption(s) in both tests_assumptions and conditional_on "
                f"(logically contradictory): {sorted(overlap)}",
            ))
    return findings


def validate_foundational_claim_deps(web: EpistemicWeb) -> list[Finding]:
    """WARNING: foundational claims are axioms and should not depend on other claims."""
    findings: list[Finding] = []
    for cid, claim in web.claims.items():
        if claim.type == ClaimType.FOUNDATIONAL and claim.depends_on:
            findings.append(Finding(
                Severity.WARNING,
                f"claims/{cid}",
                f"Foundational claim has depends_on entries "
                f"(foundational claims are axioms): {sorted(claim.depends_on)}",
            ))
    return findings


def validate_evidence_consistency(web: EpistemicWeb) -> list[Finding]:
    """WARNING: flag evidence_kind/tier combinations that are logically inconsistent.

    FIT_CHECK is a fit/consistency check by definition — it cannot simultaneously
    be a novel prediction (which would be FULLY_SPECIFIED or CONDITIONAL).
    """
    findings: list[Finding] = []
    for pid, pred in web.predictions.items():
        if (pred.tier == ConfidenceTier.FIT_CHECK
                and pred.evidence_kind == EvidenceKind.NOVEL_PREDICTION):
            findings.append(Finding(
                Severity.WARNING,
                f"predictions/{pid}",
                "FIT_CHECK prediction marked as NOVEL_PREDICTION — "
                "fit checks are definitionally not novel predictions",
            ))
    return findings


def validate_conditional_assumption_pressure(web: EpistemicWeb) -> list[Finding]:
    """WARNING: CONFIRMED/STRESSED predictions conditional on assumptions under active pressure.

    If prediction P is conditional on assumption A (A in P.conditional_on),
    and some other prediction Q that explicitly tests A (A in Q.tests_assumptions)
    has been REFUTED, then A is under adversarial pressure. P's status was
    established when A was considered sound; that basis is now in question.

    Only CONFIRMED and STRESSED predictions are flagged — PENDING predictions
    haven't been confirmed yet (no false sense of security to break), and
    REFUTED predictions are already in a terminal state.

    This does NOT automatically change any prediction's status. It surfaces
    the structural connection so the researcher cannot silently overlook it.
    """
    findings: list[Finding] = []

    # Build: assumption → set of REFUTED predictions that test it
    refuted_tests: dict = {}
    for pid, pred in web.predictions.items():
        if pred.status == PredictionStatus.REFUTED:
            for aid in pred.tests_assumptions:
                refuted_tests.setdefault(aid, set()).add(pid)

    if not refuted_tests:
        return findings

    active_statuses = {PredictionStatus.CONFIRMED, PredictionStatus.STRESSED}
    for pid, pred in web.predictions.items():
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


def validate_all(web: EpistemicWeb) -> list[Finding]:
    """Run all domain validators."""
    return (
        validate_retracted_claim_citations(web)
        + validate_tests_conditional_overlap(web)
        + validate_tier_constraints(web)
        + validate_evidence_consistency(web)
        + validate_independence_semantics(web)
        + validate_coverage(web)
        + validate_assumption_testability(web)
        + validate_implicit_assumption_coverage(web)
        + validate_foundational_claim_deps(web)
        + validate_conditional_assumption_pressure(web)
    )
