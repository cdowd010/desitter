"""Tests for epistemic/invariants.py — all 9 validators + validate_all."""
from __future__ import annotations

import pytest

from desitter.epistemic.invariants import (
    validate_all,
    validate_assumption_testability,
    validate_conditional_assumption_pressure,
    validate_coverage,
    validate_evidence_consistency,
    validate_foundational_claim_deps,
    validate_implicit_assumption_coverage,
    validate_independence_semantics,
    validate_retracted_claim_citations,
    validate_tests_conditional_overlap,
    validate_tier_constraints,
)
from desitter.epistemic.types import (
    AssumptionType,
    ClaimCategory,
    ClaimStatus,
    ClaimType,
    ConfidenceTier,
    EvidenceKind,
    MeasurementRegime,
    PredictionId,
    PredictionStatus,
    Severity,
)
from desitter.epistemic.web import EpistemicWeb

from .conftest import (
    make_analysis,
    make_analysis_id,
    make_assumption,
    make_assumption_id,
    make_claim,
    make_claim_id,
    make_group,
    make_group_id,
    make_parameter,
    make_parameter_id,
    make_prediction,
    make_prediction_id,
    make_separation,
)


# ── validate_tier_constraints ─────────────────────────────────────

class TestTierConstraints:
    def test_tier_a_with_free_params(self):
        web = EpistemicWeb()
        web = web.register_prediction(
            make_prediction(1, tier=ConfidenceTier.FULLY_SPECIFIED, free_params=2)
        )
        findings = validate_tier_constraints(web)
        critical = [f for f in findings if f.severity == Severity.CRITICAL]
        assert any("free params" in f.message for f in critical)

    def test_tier_a_zero_params_clean(self):
        web = EpistemicWeb()
        web = web.register_prediction(
            make_prediction(1, tier=ConfidenceTier.FULLY_SPECIFIED, free_params=0)
        )
        findings = validate_tier_constraints(web)
        assert not any("free params" in f.message for f in findings)

    def test_tier_b_missing_conditional_on(self):
        web = EpistemicWeb()
        web = web.register_prediction(
            make_prediction(1, tier=ConfidenceTier.CONDITIONAL, conditional_on=set())
        )
        findings = validate_tier_constraints(web)
        warnings = [f for f in findings if f.severity == Severity.WARNING]
        assert any("conditional_on" in f.message for f in warnings)

    def test_measured_without_observed(self):
        web = EpistemicWeb()
        web = web.register_prediction(
            make_prediction(
                1,
                measurement_regime=MeasurementRegime.MEASURED,
                observed=None,
            )
        )
        findings = validate_tier_constraints(web)
        assert any("observed value" in f.message for f in findings)

    def test_bound_only_without_bound(self):
        web = EpistemicWeb()
        web = web.register_prediction(
            make_prediction(
                1,
                measurement_regime=MeasurementRegime.BOUND_ONLY,
                observed_bound=None,
            )
        )
        findings = validate_tier_constraints(web)
        assert any("observed_bound" in f.message for f in findings)

    def test_tier_b_with_conditional_on_clean(self):
        web = EpistemicWeb()
        web = web.register_assumption(make_assumption(1))
        web = web.register_prediction(
            make_prediction(1, tier=ConfidenceTier.CONDITIONAL, conditional_on={make_assumption_id(1)})
        )
        findings = validate_tier_constraints(web)
        assert not any("conditional_on" in f.message for f in findings)


# ── validate_independence_semantics ───────────────────────────────

class TestIndependenceSemantics:
    def test_missing_pairwise_separation(self):
        # Both groups must have member predictions before the separation
        # requirement kicks in.
        web = EpistemicWeb()
        web = web.register_independence_group(make_group(1))
        web = web.register_independence_group(make_group(2))
        web = web.register_prediction(make_prediction(1, independence_group=make_group_id(1)))
        web = web.register_prediction(make_prediction(2, independence_group=make_group_id(2)))
        findings = validate_independence_semantics(web)
        assert any("Missing pairwise" in f.message for f in findings)

    def test_groups_without_predictions_require_no_separation(self):
        # Two empty groups: no separation needed — prevents the registration
        # deadlock where the separation requires both groups and the second
        # group requires the separation.
        web = EpistemicWeb()
        web = web.register_independence_group(make_group(1))
        web = web.register_independence_group(make_group(2))
        findings = validate_independence_semantics(web)
        assert not any("Missing pairwise" in f.message for f in findings)

    def test_one_empty_group_no_separation_needed(self):
        # IG-001 has predictions, IG-002 does not — no separation required yet.
        web = EpistemicWeb()
        web = web.register_independence_group(make_group(1))
        web = web.register_independence_group(make_group(2))
        web = web.register_prediction(make_prediction(1, independence_group=make_group_id(1)))
        findings = validate_independence_semantics(web)
        assert not any("Missing pairwise" in f.message for f in findings)

    def test_complete_pairwise(self):
        web = EpistemicWeb()
        web = web.register_independence_group(make_group(1))
        web = web.register_independence_group(make_group(2))
        web = web.register_prediction(make_prediction(1, independence_group=make_group_id(1)))
        web = web.register_prediction(make_prediction(2, independence_group=make_group_id(2)))
        web = web.add_pairwise_separation(make_separation(1))
        findings = validate_independence_semantics(web)
        assert not any("Missing pairwise" in f.message for f in findings)

    def test_group_member_backref_mismatch_detected(self, rich_web):
        web = rich_web.register_independence_group(make_group(2))
        # Inject inconsistent state directly: P-001 still points at IG-001,
        # but IG-002 also claims membership.
        web.independence_groups[make_group_id(2)].member_predictions.add(make_prediction_id(1))
        findings = validate_independence_semantics(web)
        assert any("doesn't back-reference" in f.message for f in findings)

    def test_orphan_group_member_is_ignored(self):
        web = EpistemicWeb().register_independence_group(make_group(1))
        web.independence_groups[make_group_id(1)].member_predictions.add(PredictionId("P-404"))
        findings = validate_independence_semantics(web)
        assert findings == []

    def test_three_groups_report_each_missing_pair(self):
        web = EpistemicWeb()
        web = web.register_independence_group(make_group(1))
        web = web.register_independence_group(make_group(2))
        web = web.register_independence_group(make_group(3))
        # Populate all three groups so the separation requirement applies.
        web = web.register_prediction(make_prediction(1, independence_group=make_group_id(1)))
        web = web.register_prediction(make_prediction(2, independence_group=make_group_id(2)))
        web = web.register_prediction(make_prediction(3, independence_group=make_group_id(3)))
        # Only (1,2) exists, so (1,3) and (2,3) should be flagged.
        web = web.add_pairwise_separation(make_separation(1, group_a=make_group_id(1), group_b=make_group_id(2)))

        findings = [f for f in validate_independence_semantics(web) if "Missing pairwise" in f.message]
        assert len(findings) == 2
        messages = {f.message for f in findings}
        assert "Missing pairwise separation for (IG-001, IG-003)" in messages
        assert "Missing pairwise separation for (IG-002, IG-003)" in messages


# ── validate_coverage ─────────────────────────────────────────────

class TestCoverage:
    def test_numerical_claim_no_analysis(self):
        web = EpistemicWeb()
        web = web.register_claim(
            make_claim(1, category=ClaimCategory.NUMERICAL)
        )
        findings = validate_coverage(web)
        assert any("Numerical claim" in f.message for f in findings)

    def test_empirical_assumption_no_consequence(self):
        web = EpistemicWeb()
        web = web.register_assumption(
            make_assumption(1, type=AssumptionType.EMPIRICAL, falsifiable_consequence=None)
        )
        findings = validate_coverage(web)
        assert any("falsifiable consequence" in f.message for f in findings)

    def test_stressed_prediction_flagged(self):
        web = EpistemicWeb()
        web = web.register_prediction(
            make_prediction(1, status=PredictionStatus.STRESSED)
        )
        findings = validate_coverage(web)
        assert any("STRESSED" in f.message for f in findings)


# ── validate_assumption_testability ───────────────────────────────

class TestAssumptionTestability:
    def test_consequence_without_tester(self):
        web = EpistemicWeb()
        web = web.register_assumption(
            make_assumption(1, falsifiable_consequence="if wrong, X happens")
        )
        findings = validate_assumption_testability(web)
        assert any("tested_by" in f.message for f in findings)

    def test_consequence_with_tester_clean(self):
        web = EpistemicWeb()
        web = web.register_assumption(
            make_assumption(1, falsifiable_consequence="if wrong, X happens")
        )
        web = web.register_prediction(
            make_prediction(1, tests_assumptions={make_assumption_id(1)})
        )
        findings = validate_assumption_testability(web)
        assert not any(make_assumption_id(1) in f.source for f in findings)

    def test_no_consequence_is_not_flagged(self):
        web = EpistemicWeb()
        web = web.register_assumption(
            make_assumption(1, falsifiable_consequence=None)
        )
        findings = validate_assumption_testability(web)
        assert findings == []


# ── validate_retracted_claim_citations ────────────────────────────

class TestRetractedClaimCitations:
    def test_prediction_cites_retracted(self):
        web = EpistemicWeb()
        web = web.register_claim(make_claim(1))
        web = web.register_prediction(
            make_prediction(1, claim_ids={make_claim_id(1)})
        )
        web = web.transition_claim(make_claim_id(1), ClaimStatus.RETRACTED)
        findings = validate_retracted_claim_citations(web)
        assert any("retracted" in f.message for f in findings)

    def test_claim_depends_on_retracted(self):
        web = EpistemicWeb()
        web = web.register_claim(make_claim(1))
        web = web.register_claim(
            make_claim(2, type=ClaimType.DERIVED, depends_on={make_claim_id(1)})
        )
        web = web.transition_claim(make_claim_id(1), ClaimStatus.RETRACTED)
        findings = validate_retracted_claim_citations(web)
        assert any("retracted" in f.message for f in findings)

    def test_no_retracted_clean(self, rich_web):
        findings = validate_retracted_claim_citations(rich_web)
        assert findings == []


# ── validate_tests_conditional_overlap ────────────────────────────

class TestTestsConditionalOverlap:
    def test_overlap_detected(self):
        web = EpistemicWeb()
        web = web.register_assumption(make_assumption(1))
        web = web.register_prediction(
            make_prediction(
                1,
                tests_assumptions={make_assumption_id(1)},
                conditional_on={make_assumption_id(1)},
            )
        )
        findings = validate_tests_conditional_overlap(web)
        assert any("contradictory" in f.message for f in findings)

    def test_no_overlap_clean(self):
        web = EpistemicWeb()
        web = web.register_assumption(make_assumption(1))
        web = web.register_assumption(make_assumption(2))
        web = web.register_prediction(
            make_prediction(
                1,
                tests_assumptions={make_assumption_id(1)},
                conditional_on={make_assumption_id(2)},
            )
        )
        findings = validate_tests_conditional_overlap(web)
        assert findings == []


# ── validate_foundational_claim_deps ──────────────────────────────

class TestFoundationalClaimDeps:
    def test_foundational_with_depends_on(self):
        web = EpistemicWeb()
        web = web.register_claim(make_claim(1))
        web = web.register_claim(
            make_claim(
                2,
                type=ClaimType.FOUNDATIONAL,
                depends_on={make_claim_id(1)},
            )
        )
        findings = validate_foundational_claim_deps(web)
        assert any("Foundational claim has depends_on" in f.message for f in findings)

    def test_foundational_no_deps_clean(self):
        web = EpistemicWeb()
        web = web.register_claim(make_claim(1))
        findings = validate_foundational_claim_deps(web)
        assert findings == []


# ── validate_evidence_consistency ─────────────────────────────────

class TestEvidenceConsistency:
    def test_tier_c_novel_prediction(self):
        web = EpistemicWeb()
        web = web.register_prediction(
            make_prediction(
                1,
                tier=ConfidenceTier.FIT_CHECK,
                evidence_kind=EvidenceKind.NOVEL_PREDICTION,
            )
        )
        findings = validate_evidence_consistency(web)
        assert any("NOVEL_PREDICTION" in f.message for f in findings)

    def test_tier_c_fit_clean(self):
        web = EpistemicWeb()
        web = web.register_prediction(
            make_prediction(
                1,
                tier=ConfidenceTier.FIT_CHECK,
                evidence_kind=EvidenceKind.FIT_CONSISTENCY,
            )
        )
        findings = validate_evidence_consistency(web)
        assert findings == []

    def test_tier_a_novel_prediction_clean(self):
        web = EpistemicWeb()
        web = web.register_prediction(
            make_prediction(
                1,
                tier=ConfidenceTier.FULLY_SPECIFIED,
                evidence_kind=EvidenceKind.NOVEL_PREDICTION,
            )
        )
        findings = validate_evidence_consistency(web)
        assert findings == []


# ── validate_implicit_assumption_coverage ─────────────────────────

class TestImplicitAssumptionCoverage:
    def test_untested_implicit_assumption(self):
        """Assumption underpins a prediction via claim chain but has no tested_by."""
        web = EpistemicWeb()
        web = web.register_assumption(make_assumption(1))
        web = web.register_claim(
            make_claim(1, assumptions={make_assumption_id(1)})
        )
        web = web.register_prediction(
            make_prediction(1, claim_ids={make_claim_id(1)})
        )
        findings = validate_implicit_assumption_coverage(web)
        assert any("no tested_by coverage" in f.message for f in findings)

    def test_tested_assumption_clean(self):
        web = EpistemicWeb()
        web = web.register_assumption(make_assumption(1))
        web = web.register_claim(
            make_claim(1, assumptions={make_assumption_id(1)})
        )
        web = web.register_prediction(
            make_prediction(
                1,
                claim_ids={make_claim_id(1)},
                tests_assumptions={make_assumption_id(1)},
            )
        )
        findings = validate_implicit_assumption_coverage(web)
        # A-001 is both implicit and explicitly tested → should NOT appear
        assert not any(make_assumption_id(1) in f.source for f in findings)


# ── validate_all ──────────────────────────────────────────────────

class TestValidateAll:
    def test_returns_all_findings(self):
        """validate_all aggregates all individual validators."""
        web = EpistemicWeb()
        web = web.register_prediction(
            make_prediction(1, tier=ConfidenceTier.FULLY_SPECIFIED, free_params=3)
        )
        findings = validate_all(web)
        assert len(findings) > 0
        sources = {f.source for f in findings}
        assert any("predictions" in s for s in sources)

    def test_clean_web(self):
        """An empty web should produce no findings."""
        findings = validate_all(EpistemicWeb())
        assert findings == []


# ── validate_conditional_assumption_pressure ──────────────────────

class TestConditionalAssumptionPressure:
    def test_confirmed_conditional_flagged_when_tester_refuted(self):
        """CONFIRMED prediction conditional on A should be flagged when A's tester is REFUTED."""
        web = EpistemicWeb()
        web = web.register_assumption(make_assumption(1))
        # P-001 tests A-001 and has been refuted.
        web = web.register_prediction(
            make_prediction(1, tests_assumptions={make_assumption_id(1)},
                            status=PredictionStatus.REFUTED)
        )
        # P-002 is CONFIRMED but conditional on A-001.
        web = web.register_prediction(
            make_prediction(2, conditional_on={make_assumption_id(1)},
                            status=PredictionStatus.CONFIRMED)
        )
        findings = validate_conditional_assumption_pressure(web)
        assert len(findings) == 1
        f = findings[0]
        assert f.severity == Severity.WARNING
        assert "P-002" in f.source
        assert "REFUTED" in f.message

    def test_stressed_conditional_also_flagged(self):
        """STRESSED predictions are also in scope — they are still active results."""
        web = EpistemicWeb()
        web = web.register_assumption(make_assumption(1))
        web = web.register_prediction(
            make_prediction(1, tests_assumptions={make_assumption_id(1)},
                            status=PredictionStatus.REFUTED)
        )
        web = web.register_prediction(
            make_prediction(2, conditional_on={make_assumption_id(1)},
                            status=PredictionStatus.STRESSED)
        )
        findings = validate_conditional_assumption_pressure(web)
        assert any("P-002" in f.source for f in findings)

    def test_pending_conditional_not_flagged(self):
        """PENDING predictions are not flagged — they haven't been confirmed yet."""
        web = EpistemicWeb()
        web = web.register_assumption(make_assumption(1))
        web = web.register_prediction(
            make_prediction(1, tests_assumptions={make_assumption_id(1)},
                            status=PredictionStatus.REFUTED)
        )
        web = web.register_prediction(
            make_prediction(2, conditional_on={make_assumption_id(1)},
                            status=PredictionStatus.PENDING)
        )
        findings = validate_conditional_assumption_pressure(web)
        assert findings == []

    def test_already_refuted_conditional_not_double_flagged(self):
        """A REFUTED conditional prediction is already terminal — no need to flag."""
        web = EpistemicWeb()
        web = web.register_assumption(make_assumption(1))
        web = web.register_prediction(
            make_prediction(1, tests_assumptions={make_assumption_id(1)},
                            status=PredictionStatus.REFUTED)
        )
        web = web.register_prediction(
            make_prediction(2, conditional_on={make_assumption_id(1)},
                            status=PredictionStatus.REFUTED)
        )
        findings = validate_conditional_assumption_pressure(web)
        assert findings == []

    def test_no_refuted_testers_clean(self):
        """If no predictions testing the conditional assumption are REFUTED, no finding."""
        web = EpistemicWeb()
        web = web.register_assumption(make_assumption(1))
        web = web.register_prediction(
            make_prediction(2, conditional_on={make_assumption_id(1)},
                            status=PredictionStatus.CONFIRMED)
        )
        findings = validate_conditional_assumption_pressure(web)
        assert findings == []

    def test_only_pending_tester_not_flagged(self):
        """A PENDING tester does not put the assumption under pressure."""
        web = EpistemicWeb()
        web = web.register_assumption(make_assumption(1))
        web = web.register_prediction(
            make_prediction(1, tests_assumptions={make_assumption_id(1)},
                            status=PredictionStatus.PENDING)
        )
        web = web.register_prediction(
            make_prediction(2, conditional_on={make_assumption_id(1)},
                            status=PredictionStatus.CONFIRMED)
        )
        findings = validate_conditional_assumption_pressure(web)
        assert findings == []

    def test_multiple_conditional_predictions_each_flagged(self):
        """Each CONFIRMED prediction conditional on a pressured assumption gets its own finding."""
        web = EpistemicWeb()
        web = web.register_assumption(make_assumption(1))
        web = web.register_prediction(
            make_prediction(1, tests_assumptions={make_assumption_id(1)},
                            status=PredictionStatus.REFUTED)
        )
        web = web.register_prediction(
            make_prediction(2, conditional_on={make_assumption_id(1)},
                            status=PredictionStatus.CONFIRMED)
        )
        web = web.register_prediction(
            make_prediction(3, conditional_on={make_assumption_id(1)},
                            status=PredictionStatus.CONFIRMED)
        )
        findings = validate_conditional_assumption_pressure(web)
        sources = {f.source for f in findings}
        assert "predictions/P-002" in sources
        assert "predictions/P-003" in sources
