"""Tests for EpistemicWeb remove methods — blocking refs and backlink teardown."""
from __future__ import annotations

import pytest

from desitter.epistemic.types import (
    AnalysisId,
    AssumptionId,
    ClaimId,
    ClaimType,
    DeadEndId,
    DiscoveryId,
    IndependenceGroupId,
    PairwiseSeparationId,
    ParameterId,
    PredictionId,
    TheoryId,
)
from desitter.epistemic.web import BrokenReferenceError, EpistemicWeb

from .conftest import (
    make_analysis,
    make_analysis_id,
    make_assumption,
    make_assumption_id,
    make_claim,
    make_claim_id,
    make_dead_end,
    make_dead_end_id,
    make_discovery,
    make_discovery_id,
    make_group,
    make_group_id,
    make_parameter,
    make_parameter_id,
    make_prediction,
    make_prediction_id,
    make_separation,
    make_sep_id,
    make_theory,
    make_theory_id,
)


# ── remove_prediction ─────────────────────────────────────────────

class TestRemovePrediction:
    def test_happy_path(self, rich_web):
        web = rich_web.remove_prediction(make_prediction_id(1))
        assert make_prediction_id(1) not in web.predictions

    def test_tested_by_teardown(self, rich_web):
        web = rich_web.remove_prediction(make_prediction_id(1))
        assert make_prediction_id(1) not in web.assumptions[make_assumption_id(1)].tested_by

    def test_group_member_teardown(self, rich_web):
        web = rich_web.remove_prediction(make_prediction_id(1))
        assert make_prediction_id(1) not in web.independence_groups[make_group_id(1)].member_predictions

    def test_theory_soft_ref_scrubbed(self, rich_web):
        """Theory.related_predictions should be scrubbed."""
        web = rich_web.register_theory(
            make_theory(2, related_predictions={make_prediction_id(1)})
        )
        web = web.remove_prediction(make_prediction_id(1))
        assert make_prediction_id(1) not in web.theories[make_theory_id(2)].related_predictions

    def test_dead_end_soft_ref_scrubbed(self, rich_web):
        web = rich_web.register_dead_end(
            make_dead_end(2, related_predictions={make_prediction_id(1)})
        )
        web = web.remove_prediction(make_prediction_id(1))
        assert make_prediction_id(1) not in web.dead_ends[make_dead_end_id(2)].related_predictions

    def test_discovery_soft_ref_scrubbed(self, rich_web):
        web = rich_web.register_discovery(
            make_discovery(2, related_predictions={make_prediction_id(1)})
        )
        web = web.remove_prediction(make_prediction_id(1))
        assert make_prediction_id(1) not in web.discoveries[make_discovery_id(2)].related_predictions

    def test_nonexistent_raises(self, empty_web):
        with pytest.raises(BrokenReferenceError):
            empty_web.remove_prediction(PredictionId("nope"))


# ── remove_claim ──────────────────────────────────────────────────

class TestRemoveClaim:
    def test_leaf_claim(self, web_with_claim_chain):
        """C-002 depends on C-001, so remove C-002 first (it's a leaf)."""
        web = web_with_claim_chain.remove_claim(make_claim_id(2))
        assert make_claim_id(2) not in web.claims

    def test_assumption_backlink_teardown(self, web_with_claim_chain):
        web = web_with_claim_chain.remove_claim(make_claim_id(2))
        assert make_claim_id(2) not in web.assumptions[make_assumption_id(2)].used_in_claims

    def test_analysis_backlink_teardown(self, web_with_params):
        web = web_with_params.register_analysis(
            make_analysis(1, uses_parameters={make_parameter_id(1)})
        )
        web = web.register_claim(make_claim(1, analyses={make_analysis_id(1)}))
        web = web.remove_claim(make_claim_id(1))
        assert make_claim_id(1) not in web.analyses[make_analysis_id(1)].claims_covered

    def test_blocked_by_dependent_claim(self, web_with_claim_chain):
        with pytest.raises(BrokenReferenceError, match="still referenced"):
            web_with_claim_chain.remove_claim(make_claim_id(1))

    def test_blocked_by_prediction(self, rich_web):
        with pytest.raises(BrokenReferenceError, match="still referenced"):
            rich_web.remove_claim(make_claim_id(1))

    def test_theory_soft_ref_scrubbed(self, rich_web):
        """Remove prediction first, then claim 2, then claim 1. Theory scrubbed."""
        web = rich_web.remove_prediction(make_prediction_id(1))
        web = web.remove_claim(make_claim_id(2))
        web = web.remove_claim(make_claim_id(1))
        assert make_claim_id(1) not in web.theories[make_theory_id(1)].related_claims

    def test_discovery_soft_ref_scrubbed(self, rich_web):
        web = rich_web.register_discovery(
            make_discovery(2, related_claims={make_claim_id(1)})
        )
        web = web.remove_prediction(make_prediction_id(1))
        web = web.remove_claim(make_claim_id(2))
        web = web.remove_claim(make_claim_id(1))
        assert make_claim_id(1) not in web.discoveries[make_discovery_id(2)].related_claims

    def test_dead_end_soft_ref_scrubbed(self, rich_web):
        web = rich_web.register_dead_end(
            make_dead_end(2, related_claims={make_claim_id(1)})
        )
        web = web.remove_prediction(make_prediction_id(1))
        web = web.remove_claim(make_claim_id(2))
        web = web.remove_claim(make_claim_id(1))
        assert make_claim_id(1) not in web.dead_ends[make_dead_end_id(2)].related_claims

    def test_group_lineage_scrubbed(self, rich_web):
        web = rich_web.remove_prediction(make_prediction_id(1))
        web = web.remove_claim(make_claim_id(2))
        web = web.remove_claim(make_claim_id(1))
        assert make_claim_id(1) not in web.independence_groups[make_group_id(1)].claim_lineage

    def test_nonexistent_raises(self, empty_web):
        with pytest.raises(BrokenReferenceError):
            empty_web.remove_claim(ClaimId("nope"))


# ── remove_assumption ─────────────────────────────────────────────

class TestRemoveAssumption:
    def test_blocked_by_claim(self, web_with_claim_chain):
        with pytest.raises(BrokenReferenceError, match="still referenced"):
            web_with_claim_chain.remove_assumption(make_assumption_id(1))

    def test_blocked_by_dependent_assumption(self, rich_web):
        """A-002 depends on A-001 → can't remove A-001."""
        with pytest.raises(BrokenReferenceError, match="still referenced"):
            rich_web.remove_assumption(make_assumption_id(1))

    def test_can_remove_orphan(self, web_with_assumptions):
        """No claims reference these assumptions yet."""
        web = web_with_assumptions.remove_assumption(make_assumption_id(1))
        assert make_assumption_id(1) not in web.assumptions

    def test_group_lineage_scrubbed(self, empty_web):
        web = empty_web.register_assumption(make_assumption(1))
        web = web.register_independence_group(
            make_group(1, assumption_lineage={make_assumption_id(1)})
        )
        web = web.remove_assumption(make_assumption_id(1))
        assert make_assumption_id(1) not in web.independence_groups[make_group_id(1)].assumption_lineage

    def test_nonexistent_raises(self, empty_web):
        with pytest.raises(BrokenReferenceError):
            empty_web.remove_assumption(AssumptionId("nope"))

    def test_blocked_by_prediction_tests_assumptions(self, web_with_assumptions):
        web = web_with_assumptions.register_prediction(
            make_prediction(1, tests_assumptions={make_assumption_id(1)})
        )
        with pytest.raises(BrokenReferenceError, match="still referenced"):
            web.remove_assumption(make_assumption_id(1))

    def test_blocked_by_prediction_conditional_on(self, web_with_assumptions):
        web = web_with_assumptions.register_prediction(
            make_prediction(1, conditional_on={make_assumption_id(1)})
        )
        with pytest.raises(BrokenReferenceError, match="still referenced"):
            web.remove_assumption(make_assumption_id(1))


# ── remove_parameter ──────────────────────────────────────────────

class TestRemoveParameter:
    def test_happy_path(self, web_with_params):
        # PAR-002 isn't used by any analysis
        web = web_with_params.remove_parameter(make_parameter_id(2))
        assert make_parameter_id(2) not in web.parameters

    def test_blocked_by_analysis(self, web_with_analysis):
        with pytest.raises(BrokenReferenceError, match="still used"):
            web_with_analysis.remove_parameter(make_parameter_id(1))

    def test_constraint_annotations_cleaned(self, web_with_params):
        web = web_with_params.register_claim(
            make_claim(1, parameter_constraints={make_parameter_id(2): "> 0"})
        )
        web = web.remove_parameter(make_parameter_id(2))
        assert make_parameter_id(2) not in web.claims[make_claim_id(1)].parameter_constraints

    def test_nonexistent_raises(self, empty_web):
        with pytest.raises(BrokenReferenceError):
            empty_web.remove_parameter(ParameterId("nope"))

    def test_removing_one_parameter_keeps_other_constraints(self, web_with_params):
        web = web_with_params.register_claim(
            make_claim(
                1,
                parameter_constraints={
                    make_parameter_id(1): "> 0",
                    make_parameter_id(2): "< 10",
                },
            )
        )
        web = web.remove_parameter(make_parameter_id(2))
        assert make_parameter_id(2) not in web.claims[make_claim_id(1)].parameter_constraints
        assert web.claims[make_claim_id(1)].parameter_constraints[make_parameter_id(1)] == "> 0"


# ── remove_analysis ───────────────────────────────────────────────

class TestRemoveAnalysis:
    def test_happy_path(self, web_with_analysis):
        # Remove claims referencing the analysis first is not needed since
        # no claims reference analysis in web_with_analysis fixture
        web = web_with_analysis.remove_analysis(make_analysis_id(1))
        assert make_analysis_id(1) not in web.analyses

    def test_parameter_backlink_teardown(self, web_with_analysis):
        web = web_with_analysis.remove_analysis(make_analysis_id(1))
        assert make_analysis_id(1) not in web.parameters[make_parameter_id(1)].used_in_analyses

    def test_blocked_by_claim(self, web_with_analysis):
        web = web_with_analysis.register_claim(
            make_claim(1, analyses={make_analysis_id(1)})
        )
        with pytest.raises(BrokenReferenceError, match="still referenced"):
            web.remove_analysis(make_analysis_id(1))

    def test_blocked_by_prediction(self, web_with_analysis):
        web = web_with_analysis.register_prediction(
            make_prediction(1, analysis=make_analysis_id(1))
        )
        with pytest.raises(BrokenReferenceError, match="still referenced"):
            web.remove_analysis(make_analysis_id(1))

    def test_nonexistent_raises(self, empty_web):
        with pytest.raises(BrokenReferenceError):
            empty_web.remove_analysis(AnalysisId("nope"))


# ── remove_independence_group ─────────────────────────────────────

class TestRemoveIndependenceGroup:
    def test_happy_path(self, empty_web):
        web = empty_web.register_independence_group(make_group(1))
        web = web.remove_independence_group(make_group_id(1))
        assert make_group_id(1) not in web.independence_groups

    def test_blocked_by_prediction(self, rich_web):
        with pytest.raises(BrokenReferenceError, match="still referenced"):
            rich_web.remove_independence_group(make_group_id(1))

    def test_blocked_by_separation(self, empty_web):
        web = empty_web.register_independence_group(make_group(1))
        web = web.register_independence_group(make_group(2))
        web = web.add_pairwise_separation(make_separation(1))
        with pytest.raises(BrokenReferenceError, match="still referenced"):
            web.remove_independence_group(make_group_id(1))

    def test_nonexistent_raises(self, empty_web):
        with pytest.raises(BrokenReferenceError):
            empty_web.remove_independence_group(IndependenceGroupId("nope"))

    def test_can_remove_after_pairwise_removed(self, empty_web):
        web = empty_web.register_independence_group(make_group(1))
        web = web.register_independence_group(make_group(2))
        web = web.add_pairwise_separation(make_separation(1))
        web = web.remove_pairwise_separation(make_sep_id(1))
        web = web.remove_independence_group(make_group_id(1))
        assert make_group_id(1) not in web.independence_groups


# ── remove_theory / discovery / dead_end / concept / pairwise_separation ─

class TestRemoveLeafEntities:
    """Leaf entities have no blocker — just existence checks."""

    def test_remove_theory(self, rich_web):
        web = rich_web.remove_theory(make_theory_id(1))
        assert make_theory_id(1) not in web.theories

    def test_remove_discovery(self, rich_web):
        web = rich_web.remove_discovery(make_discovery_id(1))
        assert make_discovery_id(1) not in web.discoveries

    def test_remove_dead_end(self, rich_web):
        web = rich_web.remove_dead_end(make_dead_end_id(1))
        assert make_dead_end_id(1) not in web.dead_ends

    def test_remove_pairwise_separation(self, empty_web):
        web = empty_web.register_independence_group(make_group(1))
        web = web.register_independence_group(make_group(2))
        web = web.add_pairwise_separation(make_separation(1))
        web = web.remove_pairwise_separation(make_sep_id(1))
        assert make_sep_id(1) not in web.pairwise_separations

    def test_remove_theory_nonexistent(self, empty_web):
        with pytest.raises(BrokenReferenceError):
            empty_web.remove_theory(TheoryId("nope"))

    def test_remove_discovery_nonexistent(self, empty_web):
        with pytest.raises(BrokenReferenceError):
            empty_web.remove_discovery(DiscoveryId("nope"))

    def test_remove_dead_end_nonexistent(self, empty_web):
        with pytest.raises(BrokenReferenceError):
            empty_web.remove_dead_end(DeadEndId("nope"))

    def test_remove_separation_nonexistent(self, empty_web):
        with pytest.raises(BrokenReferenceError):
            empty_web.remove_pairwise_separation(PairwiseSeparationId("nope"))
