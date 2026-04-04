"""Validation rules that span multiple entities.

These require looking at the web as a whole. Each function is pure:
(EpistemicWeb) -> list[Finding].

Structural invariants (refs exist, no cycles, bidirectional links) live
in web.py and are enforced at mutation time.

Semantic/coverage invariants live here and are checked on demand.
"""
from __future__ import annotations

from .types import Finding, Severity
from .web import EpistemicWeb


def validate_tier_constraints(web: EpistemicWeb) -> list[Finding]:
    """Tier A: 0 free params. Tier B: must state conditional_on."""
    findings: list[Finding] = []
    for pid, pred in web.predictions.items():
        if pred.tier.value == "A" and pred.free_params != 0:
            findings.append(Finding(
                Severity.CRITICAL,
                f"predictions/{pid}",
                f"Tier A prediction has {pred.free_params} free params (must be 0)",
            ))
        if pred.tier.value == "B" and not pred.conditional_on:
            findings.append(Finding(
                Severity.WARNING,
                f"predictions/{pid}",
                "Tier B prediction missing 'conditional_on'",
            ))
        if pred.measurement_regime.value == "measured" and pred.observed is None:
            findings.append(Finding(
                Severity.CRITICAL,
                f"predictions/{pid}",
                "measurement_regime='measured' requires an observed value",
            ))
        if pred.measurement_regime.value == "bound_only" and pred.observed_bound is None:
            findings.append(Finding(
                Severity.CRITICAL,
                f"predictions/{pid}",
                "measurement_regime='bound_only' requires observed_bound",
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

    # Check pairwise separation completeness
    group_ids = sorted(web.independence_groups.keys())
    seen_pairs: set[tuple[str, str]] = set()
    for ps in web.pairwise_separations.values():
        pair = (min(ps.group_a, ps.group_b), max(ps.group_a, ps.group_b))
        seen_pairs.add(pair)

    for i, a in enumerate(group_ids):
        for b in group_ids[i + 1:]:
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
        if claim.category == "numerical" and not claim.analyses:
            findings.append(Finding(
                Severity.INFO,
                f"claims/{cid}",
                "Numerical claim has no linked analyses",
            ))

    for aid, assumption in web.assumptions.items():
        if assumption.type == "E" and not assumption.falsifiable_consequence:
            findings.append(Finding(
                Severity.WARNING,
                f"assumptions/{aid}",
                "Empirical [E] assumption has no falsifiable consequence",
            ))

    stressed = [
        pid for pid, p in web.predictions.items()
        if p.status.value == "STRESSED"
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


def validate_all(web: EpistemicWeb) -> list[Finding]:
    """Run all domain validators."""
    return (
        validate_tier_constraints(web)
        + validate_independence_semantics(web)
        + validate_coverage(web)
        + validate_assumption_testability(web)
        + validate_implicit_assumption_coverage(web)
    )
