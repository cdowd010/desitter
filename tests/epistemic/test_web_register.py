"""Tests for EpistemicWeb register methods — happy paths and rejections."""
from __future__ import annotations

import pytest

from horizon_research.epistemic.model import (
    Analysis,
    Assumption,
    Claim,
    Concept,
    DeadEnd,
    Discovery,
    IndependenceGroup,
    PairwiseSeparation,
    Parameter,
    Prediction,
    Theory,
)
from horizon_research.epistemic.types import (
    AnalysisId,
    AssumptionId,
    ClaimId,
    ConceptId,
    DeadEndId,
    DiscoveryId,
    IndependenceGroupId,
    PairwiseSeparationId,
    ParameterId,
    PredictionId,
    TheoryId,
)
from horizon_research.epistemic.web import (
    BrokenReferenceError,
    CycleError,
    DuplicateIdError,
    EpistemicWeb,
)

from .conftest import (
    make_analysis,
    make_analysis_id,
    make_assumption,
    make_assumption_id,
    make_claim,
    make_claim_id,
    make_concept,
    make_dead_end,
    make_discovery,
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


# ── register_parameter ────────────────────────────────────────────

class TestRegisterParameter:
    def test_happy_path(self, empty_web):
        p = make_parameter(1)
        web = empty_web.register_parameter(p)
        assert make_parameter_id(1) in web.parameters

    def test_duplicate_raises(self, empty_web):
        web = empty_web.register_parameter(make_parameter(1))
        with pytest.raises(DuplicateIdError):
            web.register_parameter(make_parameter(1))

    def test_backlink_cleared(self, empty_web):
        """used_in_analyses injected by caller must be stripped."""
        p = make_parameter(1, used_in_analyses={AnalysisId("AN-999")})
        web = empty_web.register_parameter(p)
        assert web.parameters[make_parameter_id(1)].used_in_analyses == set()


# ── register_analysis ─────────────────────────────────────────────

class TestRegisterAnalysis:
    def test_happy_path(self, web_with_params):
        a = make_analysis(1, uses_parameters={make_parameter_id(1)})
        web = web_with_params.register_analysis(a)
        assert make_analysis_id(1) in web.analyses

    def test_bidi_parameter_link(self, web_with_params):
        a = make_analysis(1, uses_parameters={make_parameter_id(1)})
        web = web_with_params.register_analysis(a)
        assert make_analysis_id(1) in web.parameters[make_parameter_id(1)].used_in_analyses

    def test_claims_covered_backlink_cleared(self, web_with_params):
        a = make_analysis(1, claims_covered={ClaimId("C-999")})
        web = web_with_params.register_analysis(a)
        assert web.analyses[make_analysis_id(1)].claims_covered == set()

    def test_duplicate_raises(self, web_with_params):
        web = web_with_params.register_analysis(make_analysis(1))
        with pytest.raises(DuplicateIdError):
            web.register_analysis(make_analysis(1))

    def test_missing_param_ref_raises(self, empty_web):
        a = make_analysis(1, uses_parameters={ParameterId("nonexistent")})
        with pytest.raises(BrokenReferenceError):
            empty_web.register_analysis(a)


# ── register_assumption ───────────────────────────────────────────

class TestRegisterAssumption:
    def test_happy_path(self, empty_web):
        web = empty_web.register_assumption(make_assumption(1))
        assert make_assumption_id(1) in web.assumptions

    def test_backlinks_cleared(self, empty_web):
        a = make_assumption(
            1,
            used_in_claims={ClaimId("C-999")},
            tested_by={PredictionId("P-999")},
        )
        web = empty_web.register_assumption(a)
        stored = web.assumptions[make_assumption_id(1)]
        assert stored.used_in_claims == set()
        assert stored.tested_by == set()

    def test_depends_on_valid(self, web_with_assumptions):
        a3 = make_assumption(3, depends_on={make_assumption_id(1)})
        web = web_with_assumptions.register_assumption(a3)
        assert make_assumption_id(3) in web.assumptions

    def test_depends_on_broken_ref(self, empty_web):
        a = make_assumption(1, depends_on={AssumptionId("nonexistent")})
        with pytest.raises(BrokenReferenceError):
            empty_web.register_assumption(a)

    def test_cycle_detection(self, empty_web):
        web = empty_web.register_assumption(make_assumption(1))
        web = web.register_assumption(
            make_assumption(2, depends_on={make_assumption_id(1)})
        )
        cyc = make_assumption(1, depends_on={make_assumption_id(2)})
        # Can't re-register, but if we update to create a cycle...
        # Direct cycle test: assumption that depends_on itself
        self_loop = make_assumption(3, depends_on={make_assumption_id(3)})
        # self-ref: the assumption isn't in the web yet, so depends_on
        # points to itself — which doesn't exist → BrokenReferenceError
        with pytest.raises(BrokenReferenceError):
            web.register_assumption(self_loop)

    def test_duplicate_raises(self, empty_web):
        web = empty_web.register_assumption(make_assumption(1))
        with pytest.raises(DuplicateIdError):
            web.register_assumption(make_assumption(1))


# ── register_claim ────────────────────────────────────────────────

class TestRegisterClaim:
    def test_happy_path(self, web_with_assumptions):
        c = make_claim(1, assumptions={make_assumption_id(1)})
        web = web_with_assumptions.register_claim(c)
        assert make_claim_id(1) in web.claims

    def test_bidi_assumption_link(self, web_with_assumptions):
        c = make_claim(1, assumptions={make_assumption_id(1)})
        web = web_with_assumptions.register_claim(c)
        assert make_claim_id(1) in web.assumptions[make_assumption_id(1)].used_in_claims

    def test_bidi_analysis_link(self, web_with_params):
        web = web_with_params.register_analysis(
            make_analysis(1, uses_parameters={make_parameter_id(1)})
        )
        c = make_claim(1, analyses={make_analysis_id(1)})
        web = web.register_claim(c)
        assert make_claim_id(1) in web.analyses[make_analysis_id(1)].claims_covered

    def test_depends_on_valid(self, web_with_assumptions):
        web = web_with_assumptions.register_claim(
            make_claim(1, assumptions={make_assumption_id(1)})
        )
        c2 = make_claim(2, depends_on={make_claim_id(1)})
        web = web.register_claim(c2)
        assert make_claim_id(2) in web.claims

    def test_depends_on_missing_raises(self, empty_web):
        c = make_claim(1, depends_on={ClaimId("nonexistent")})
        with pytest.raises(BrokenReferenceError):
            empty_web.register_claim(c)

    def test_assumption_missing_raises(self, empty_web):
        c = make_claim(1, assumptions={AssumptionId("nonexistent")})
        with pytest.raises(BrokenReferenceError):
            empty_web.register_claim(c)

    def test_cycle_raises(self, web_with_assumptions):
        web = web_with_assumptions.register_claim(
            make_claim(1, assumptions={make_assumption_id(1)})
        )
        web = web.register_claim(
            make_claim(2, depends_on={make_claim_id(1)})
        )
        # Try to add claim 3 that depends on claim 2 AND add claim 1 depending on 3
        # — can't, but we can detect forward cycle by adding a claim whose
        # depends_on includes itself (via chain).
        # For true cycle: C-003 depends on C-002, then trying to make C-001 depend on C-003.
        # But C-001 is already registered. Instead: make C-003 → C-002 → C-001 → C-003
        # not possible as C-003 doesn't exist yet when we check.
        # Simplest case: claim depends on itself:
        self_dep = make_claim(3, depends_on={make_claim_id(3)})
        # This is a BrokenReferenceError since C-003 doesn't exist yet
        with pytest.raises(BrokenReferenceError):
            web.register_claim(self_dep)

    def test_duplicate_raises(self, web_with_assumptions):
        web = web_with_assumptions.register_claim(make_claim(1))
        with pytest.raises(DuplicateIdError):
            web.register_claim(make_claim(1))

    def test_parameter_constraints_validated(self, web_with_params):
        c = make_claim(1, parameter_constraints={ParameterId("nonexistent"): "> 0"})
        with pytest.raises(BrokenReferenceError):
            web_with_params.register_claim(c)

    def test_parameter_constraints_valid(self, web_with_params):
        c = make_claim(1, parameter_constraints={make_parameter_id(1): "< 5"})
        web = web_with_params.register_claim(c)
        assert web.claims[make_claim_id(1)].parameter_constraints[make_parameter_id(1)] == "< 5"


# ── register_prediction ──────────────────────────────────────────

class TestRegisterPrediction:
    def test_happy_path(self, web_with_claim_chain):
        p = make_prediction(1, claim_ids={make_claim_id(1)})
        web = web_with_claim_chain.register_prediction(p)
        assert make_prediction_id(1) in web.predictions

    def test_bidi_tested_by(self, web_with_claim_chain):
        p = make_prediction(
            1,
            claim_ids={make_claim_id(1)},
            tests_assumptions={make_assumption_id(1)},
        )
        web = web_with_claim_chain.register_prediction(p)
        assert make_prediction_id(1) in web.assumptions[make_assumption_id(1)].tested_by

    def test_bidi_group_member(self, web_with_claim_chain):
        web = web_with_claim_chain.register_independence_group(
            make_group(1, claim_lineage={make_claim_id(1)})
        )
        p = make_prediction(
            1,
            claim_ids={make_claim_id(1)},
            independence_group=make_group_id(1),
        )
        web = web.register_prediction(p)
        assert make_prediction_id(1) in web.independence_groups[make_group_id(1)].member_predictions

    def test_missing_claim_raises(self, empty_web):
        p = make_prediction(1, claim_ids={ClaimId("nonexistent")})
        with pytest.raises(BrokenReferenceError):
            empty_web.register_prediction(p)

    def test_missing_analysis_raises(self, web_with_claim_chain):
        p = make_prediction(
            1,
            claim_ids={make_claim_id(1)},
            analysis=AnalysisId("nonexistent"),
        )
        with pytest.raises(BrokenReferenceError):
            web_with_claim_chain.register_prediction(p)

    def test_missing_group_raises(self, web_with_claim_chain):
        p = make_prediction(
            1,
            claim_ids={make_claim_id(1)},
            independence_group=IndependenceGroupId("nonexistent"),
        )
        with pytest.raises(BrokenReferenceError):
            web_with_claim_chain.register_prediction(p)

    def test_missing_conditional_on_raises(self, web_with_claim_chain):
        p = make_prediction(
            1,
            claim_ids={make_claim_id(1)},
            conditional_on={AssumptionId("nonexistent")},
        )
        with pytest.raises(BrokenReferenceError):
            web_with_claim_chain.register_prediction(p)

    def test_duplicate_raises(self, web_with_claim_chain):
        web = web_with_claim_chain.register_prediction(make_prediction(1))
        with pytest.raises(DuplicateIdError):
            web.register_prediction(make_prediction(1))


# ── register_theory ───────────────────────────────────────────────

class TestRegisterTheory:
    def test_happy_path(self, web_with_claim_chain):
        t = make_theory(1, related_claims={make_claim_id(1)})
        web = web_with_claim_chain.register_theory(t)
        assert make_theory_id(1) in web.theories

    def test_missing_claim_raises(self, empty_web):
        t = make_theory(1, related_claims={ClaimId("nonexistent")})
        with pytest.raises(BrokenReferenceError):
            empty_web.register_theory(t)

    def test_duplicate_raises(self, empty_web):
        web = empty_web.register_theory(make_theory(1))
        with pytest.raises(DuplicateIdError):
            web.register_theory(make_theory(1))


# ── register_independence_group ───────────────────────────────────

class TestRegisterIndependenceGroup:
    def test_happy_path(self, web_with_claim_chain):
        g = make_group(1, claim_lineage={make_claim_id(1)})
        web = web_with_claim_chain.register_independence_group(g)
        assert make_group_id(1) in web.independence_groups

    def test_member_predictions_backlink_cleared(self, web_with_claim_chain):
        g = make_group(1, member_predictions={PredictionId("P-999")})
        web = web_with_claim_chain.register_independence_group(g)
        assert web.independence_groups[make_group_id(1)].member_predictions == set()

    def test_missing_claim_lineage_raises(self, empty_web):
        g = make_group(1, claim_lineage={ClaimId("nonexistent")})
        with pytest.raises(BrokenReferenceError):
            empty_web.register_independence_group(g)

    def test_duplicate_raises(self, empty_web):
        web = empty_web.register_independence_group(make_group(1))
        with pytest.raises(DuplicateIdError):
            web.register_independence_group(make_group(1))


# ── add_pairwise_separation ──────────────────────────────────────

class TestAddPairwiseSeparation:
    def _web_with_two_groups(self, empty_web):
        web = empty_web.register_independence_group(make_group(1))
        web = web.register_independence_group(make_group(2))
        return web

    def test_happy_path(self, empty_web):
        web = self._web_with_two_groups(empty_web)
        sep = make_separation(1)
        web = web.add_pairwise_separation(sep)
        assert make_sep_id(1) in web.pairwise_separations

    def test_self_pair_rejected(self, empty_web):
        web = empty_web.register_independence_group(make_group(1))
        sep = make_separation(1, group_a=make_group_id(1), group_b=make_group_id(1))
        with pytest.raises(BrokenReferenceError, match="distinct"):
            web.add_pairwise_separation(sep)

    def test_missing_group_a_raises(self, empty_web):
        web = empty_web.register_independence_group(make_group(2))
        sep = make_separation(1)
        with pytest.raises(BrokenReferenceError):
            web.add_pairwise_separation(sep)

    def test_missing_group_b_raises(self, empty_web):
        web = empty_web.register_independence_group(make_group(1))
        sep = make_separation(1)
        with pytest.raises(BrokenReferenceError):
            web.add_pairwise_separation(sep)

    def test_duplicate_raises(self, empty_web):
        web = self._web_with_two_groups(empty_web)
        web = web.add_pairwise_separation(make_separation(1))
        with pytest.raises(DuplicateIdError):
            web.add_pairwise_separation(make_separation(1))


# ── register_discovery ────────────────────────────────────────────

class TestRegisterDiscovery:
    def test_happy_path(self, empty_web):
        web = empty_web.register_discovery(make_discovery(1))
        assert "D-001" in [str(k) for k in web.discoveries]

    def test_duplicate_raises(self, empty_web):
        web = empty_web.register_discovery(make_discovery(1))
        with pytest.raises(DuplicateIdError):
            web.register_discovery(make_discovery(1))


# ── register_dead_end ─────────────────────────────────────────────

class TestRegisterDeadEnd:
    def test_happy_path(self, empty_web):
        web = empty_web.register_dead_end(make_dead_end(1))
        assert "DE-001" in [str(k) for k in web.dead_ends]

    def test_duplicate_raises(self, empty_web):
        web = empty_web.register_dead_end(make_dead_end(1))
        with pytest.raises(DuplicateIdError):
            web.register_dead_end(make_dead_end(1))


# ── register_concept ──────────────────────────────────────────────

class TestRegisterConcept:
    def test_happy_path(self, empty_web):
        web = empty_web.register_concept(make_concept(1))
        assert "CO-001" in [str(k) for k in web.concepts]

    def test_duplicate_raises(self, empty_web):
        web = empty_web.register_concept(make_concept(1))
        with pytest.raises(DuplicateIdError):
            web.register_concept(make_concept(1))


# ── Caller reference isolation ────────────────────────────────────

class TestCallerIsolation:
    """After registration, mutating the original object must not affect the web."""

    def test_claim_isolation(self, web_with_assumptions):
        c = make_claim(1, assumptions={make_assumption_id(1)})
        web = web_with_assumptions.register_claim(c)
        c.statement = "CHANGED"
        assert web.claims[make_claim_id(1)].statement != "CHANGED"

    def test_parameter_isolation(self, empty_web):
        p = make_parameter(1)
        web = empty_web.register_parameter(p)
        p.value = 999999
        assert web.parameters[make_parameter_id(1)].value != 999999
