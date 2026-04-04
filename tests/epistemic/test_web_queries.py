"""Tests for EpistemicWeb query methods."""
from __future__ import annotations

import pytest

from horizon_research.epistemic.types import (
    AnalysisId,
    AssumptionId,
    ClaimId,
    ClaimType,
    ConfidenceTier,
    EvidenceKind,
    IndependenceGroupId,
    MeasurementRegime,
    ParameterId,
    PredictionId,
    PredictionStatus,
)
from horizon_research.epistemic.web import EpistemicWeb

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
)


# ── get_claim / get_assumption / get_prediction ──────────────────

class TestSimpleGetters:
    def test_get_claim_present(self, rich_web):
        assert rich_web.get_claim(make_claim_id(1)) is not None

    def test_get_claim_absent(self, rich_web):
        assert rich_web.get_claim(ClaimId("nonexistent")) is None

    def test_get_assumption_present(self, rich_web):
        assert rich_web.get_assumption(make_assumption_id(1)) is not None

    def test_get_assumption_absent(self, rich_web):
        assert rich_web.get_assumption(AssumptionId("nope")) is None

    def test_get_prediction_present(self, rich_web):
        assert rich_web.get_prediction(make_prediction_id(1)) is not None

    def test_get_prediction_absent(self, rich_web):
        assert rich_web.get_prediction(PredictionId("nope")) is None


# ── claims_using_assumption ───────────────────────────────────────

class TestClaimsUsingAssumption:
    def test_one_claim(self, rich_web):
        result = rich_web.claims_using_assumption(make_assumption_id(1))
        assert make_claim_id(1) in result

    def test_no_claims(self, web_with_assumptions):
        result = web_with_assumptions.claims_using_assumption(make_assumption_id(1))
        assert result == set()


# ── claim_lineage ─────────────────────────────────────────────────

class TestClaimLineage:
    def test_single_parent(self, web_with_claim_chain):
        ancestors = web_with_claim_chain.claim_lineage(make_claim_id(2))
        assert ancestors == {make_claim_id(1)}

    def test_root_has_no_ancestors(self, web_with_claim_chain):
        ancestors = web_with_claim_chain.claim_lineage(make_claim_id(1))
        assert ancestors == set()

    def test_transitive(self, web_with_assumptions):
        """C1 ← C2 ← C3: lineage of C3 = {C1, C2}."""
        web = web_with_assumptions
        web = web.register_claim(make_claim(1))
        web = web.register_claim(
            make_claim(2, type=ClaimType.DERIVED, depends_on={make_claim_id(1)})
        )
        web = web.register_claim(
            make_claim(3, type=ClaimType.DERIVED, depends_on={make_claim_id(2)})
        )
        assert web.claim_lineage(make_claim_id(3)) == {make_claim_id(1), make_claim_id(2)}

    def test_nonexistent_claim(self, empty_web):
        assert empty_web.claim_lineage(ClaimId("nope")) == set()


# ── assumption_lineage ────────────────────────────────────────────

class TestAssumptionLineage:
    def test_direct(self, web_with_claim_chain):
        lineage = web_with_claim_chain.assumption_lineage(make_claim_id(1))
        assert make_assumption_id(1) in lineage

    def test_through_depends_on(self, rich_web):
        """C-002 depends on C-001. C-001 uses A-001. A-002 depends on A-001.
        So assumption_lineage(C-002) should include A-001 and A-002."""
        lineage = rich_web.assumption_lineage(make_claim_id(2))
        assert make_assumption_id(1) in lineage
        assert make_assumption_id(2) in lineage

    def test_nonexistent_claim(self, empty_web):
        assert empty_web.assumption_lineage(ClaimId("nope")) == set()


# ── prediction_implicit_assumptions ──────────────────────────────

class TestPredictionImplicitAssumptions:
    def test_basic(self, rich_web):
        """P-001 references C-001 and C-002. Should surface A-001 and A-002."""
        result = rich_web.prediction_implicit_assumptions(make_prediction_id(1))
        assert make_assumption_id(1) in result
        assert make_assumption_id(2) in result

    def test_conditional_on_expanded(self, web_with_assumptions):
        """conditional_on assumptions and their depends_on chains are included."""
        web = web_with_assumptions
        web = web.register_assumption(
            make_assumption(3, depends_on={make_assumption_id(1)})
        )
        web = web.register_claim(make_claim(1))
        web = web.register_prediction(
            make_prediction(1, conditional_on={make_assumption_id(3)})
        )
        result = web.prediction_implicit_assumptions(make_prediction_id(1))
        assert make_assumption_id(3) in result
        assert make_assumption_id(1) in result  # transitive through depends_on

    def test_nonexistent_prediction(self, empty_web):
        assert empty_web.prediction_implicit_assumptions(PredictionId("nope")) == set()


# ── refutation_impact ─────────────────────────────────────────────

class TestRefutationImpact:
    def test_basic(self, rich_web):
        impact = rich_web.refutation_impact(make_prediction_id(1))
        assert make_claim_id(1) in impact["claim_ids"]
        assert make_claim_id(2) in impact["claim_ids"]
        assert make_assumption_id(1) in impact["implicit_assumptions"]

    def test_nonexistent(self, empty_web):
        impact = empty_web.refutation_impact(PredictionId("nope"))
        assert impact["claim_ids"] == set()


# ── assumption_support_status ─────────────────────────────────────

class TestAssumptionSupportStatus:
    def test_basic(self, rich_web):
        status = rich_web.assumption_support_status(make_assumption_id(1))
        assert make_claim_id(1) in status["direct_claims"]
        assert make_prediction_id(1) in status["dependent_predictions"]
        assert make_prediction_id(1) in status["tested_by"]

    def test_nonexistent(self, empty_web):
        status = empty_web.assumption_support_status(AssumptionId("nope"))
        assert status["direct_claims"] == set()


# ── claims_depending_on_claim ─────────────────────────────────────

class TestClaimsDependingOnClaim:
    def test_downstream(self, web_with_claim_chain):
        downstream = web_with_claim_chain.claims_depending_on_claim(make_claim_id(1))
        assert make_claim_id(2) in downstream

    def test_leaf_has_no_dependants(self, web_with_claim_chain):
        assert web_with_claim_chain.claims_depending_on_claim(make_claim_id(2)) == set()


# ── predictions_depending_on_claim ────────────────────────────────

class TestPredictionsDependingOnClaim:
    def test_direct(self, rich_web):
        preds = rich_web.predictions_depending_on_claim(make_claim_id(1))
        assert make_prediction_id(1) in preds

    def test_through_dependent_claim(self, rich_web):
        """P-001 references C-002 which depends on C-001.
        So predictions_depending_on_claim(C-001) should include P-001."""
        preds = rich_web.predictions_depending_on_claim(make_claim_id(1))
        assert make_prediction_id(1) in preds


# ── parameter_impact ──────────────────────────────────────────────

class TestParameterImpact:
    def test_basic(self, rich_web):
        impact = rich_web.parameter_impact(make_parameter_id(1))
        assert make_analysis_id(1) in impact["stale_analyses"]
        # Analysis 1 covers claim 1 (via bidi link from register_claim)
        assert make_claim_id(1) in impact["affected_claims"]
        assert make_prediction_id(1) in impact["affected_predictions"]

    def test_parameter_constraints(self):
        """Claims with parameter_constraints should show up in constrained_claims."""
        web = EpistemicWeb()
        web = web.register_parameter(make_parameter(1))
        web = web.register_claim(
            make_claim(1, parameter_constraints={make_parameter_id(1): "> 0"})
        )
        impact = web.parameter_impact(make_parameter_id(1))
        assert make_claim_id(1) in impact["constrained_claims"]

    def test_nonexistent(self, empty_web):
        impact = empty_web.parameter_impact(ParameterId("nope"))
        assert impact["stale_analyses"] == set()

    def test_prediction_linked_to_stale_analysis(self):
        """Predictions whose analysis field points to a stale analysis appear."""
        web = EpistemicWeb()
        web = web.register_parameter(make_parameter(1))
        web = web.register_analysis(
            make_analysis(1, uses_parameters={make_parameter_id(1)})
        )
        web = web.register_prediction(
            make_prediction(1, analysis=make_analysis_id(1))
        )
        impact = web.parameter_impact(make_parameter_id(1))
        assert make_prediction_id(1) in impact["affected_predictions"]
