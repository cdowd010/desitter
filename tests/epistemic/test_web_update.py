"""Tests for EpistemicWeb update methods — bidirectional link diffing."""
from __future__ import annotations

import copy

import pytest

from horizon_research.epistemic.types import (
    AnalysisId,
    AssumptionId,
    AssumptionType,
    ClaimId,
    ClaimType,
    ConfidenceTier,
    EvidenceKind,
    IndependenceGroupId,
    MeasurementRegime,
    ParameterId,
    PredictionId,
    PredictionStatus,
    TheoryStatus,
)
from horizon_research.epistemic.web import BrokenReferenceError, EpistemicWeb

from .conftest import (
    make_analysis,
    make_analysis_id,
    make_assumption,
    make_assumption_id,
    make_claim,
    make_claim_id,
    make_concept,
    make_concept_id,
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


# ── update_claim ──────────────────────────────────────────────────

class TestUpdateClaim:
    def test_statement_change(self, web_with_claim_chain):
        old = web_with_claim_chain.get_claim(make_claim_id(1))
        updated = copy.deepcopy(old)
        updated.statement = "revised statement"
        web = web_with_claim_chain.update_claim(updated)
        assert web.claims[make_claim_id(1)].statement == "revised statement"

    def test_assumption_link_diff(self, web_with_assumptions):
        """Move claim from assumption 1 to assumption 2 → backlinks update."""
        web = web_with_assumptions.register_claim(
            make_claim(1, assumptions={make_assumption_id(1)})
        )
        updated = copy.deepcopy(web.claims[make_claim_id(1)])
        updated.assumptions = {make_assumption_id(2)}
        web2 = web.update_claim(updated)
        assert make_claim_id(1) not in web2.assumptions[make_assumption_id(1)].used_in_claims
        assert make_claim_id(1) in web2.assumptions[make_assumption_id(2)].used_in_claims

    def test_analysis_link_diff(self, web_with_params):
        web = web_with_params.register_analysis(
            make_analysis(1, uses_parameters={make_parameter_id(1)})
        )
        web = web.register_analysis(make_analysis(2))
        web = web.register_claim(make_claim(1, analyses={make_analysis_id(1)}))
        updated = copy.deepcopy(web.claims[make_claim_id(1)])
        updated.analyses = {make_analysis_id(2)}
        web2 = web.update_claim(updated)
        assert make_claim_id(1) not in web2.analyses[make_analysis_id(1)].claims_covered
        assert make_claim_id(1) in web2.analyses[make_analysis_id(2)].claims_covered

    def test_nonexistent_raises(self, empty_web):
        with pytest.raises(BrokenReferenceError):
            empty_web.update_claim(make_claim(99))

    def test_broken_ref_raises(self, web_with_claim_chain):
        updated = copy.deepcopy(web_with_claim_chain.claims[make_claim_id(1)])
        updated.assumptions = {AssumptionId("nonexistent")}
        with pytest.raises(BrokenReferenceError):
            web_with_claim_chain.update_claim(updated)


# ── update_assumption ─────────────────────────────────────────────

class TestUpdateAssumption:
    def test_statement_change(self, web_with_assumptions):
        old = web_with_assumptions.assumptions[make_assumption_id(1)]
        updated = copy.deepcopy(old)
        updated.statement = "new wording"
        web = web_with_assumptions.update_assumption(updated)
        assert web.assumptions[make_assumption_id(1)].statement == "new wording"

    def test_preserves_backlinks(self, web_with_claim_chain):
        """used_in_claims and tested_by are owned by claims/predictions — preserved."""
        web = web_with_claim_chain
        old = web.assumptions[make_assumption_id(1)]
        # After registering claim 1 with assumption 1, used_in_claims should have C-001
        assert make_claim_id(1) in old.used_in_claims
        updated = copy.deepcopy(old)
        updated.statement = "updated"
        web2 = web.update_assumption(updated)
        assert make_claim_id(1) in web2.assumptions[make_assumption_id(1)].used_in_claims

    def test_nonexistent_raises(self, empty_web):
        with pytest.raises(BrokenReferenceError):
            empty_web.update_assumption(make_assumption(99))


# ── update_prediction ─────────────────────────────────────────────

class TestUpdatePrediction:
    def test_basic_field_change(self, rich_web):
        old = rich_web.predictions[make_prediction_id(1)]
        updated = copy.deepcopy(old)
        updated.observed = 42.0
        web = rich_web.update_prediction(updated)
        assert web.predictions[make_prediction_id(1)].observed == 42.0

    def test_tested_by_diff(self, rich_web):
        """Remove A-001 from tests_assumptions → A-001.tested_by loses P-001."""
        old = rich_web.predictions[make_prediction_id(1)]
        updated = copy.deepcopy(old)
        updated.tests_assumptions = set()
        web = rich_web.update_prediction(updated)
        assert make_prediction_id(1) not in web.assumptions[make_assumption_id(1)].tested_by

    def test_group_change(self, rich_web):
        """Move prediction to a different group → old group loses member, new gains it."""
        web = rich_web.register_independence_group(make_group(2))
        old = web.predictions[make_prediction_id(1)]
        updated = copy.deepcopy(old)
        updated.independence_group = make_group_id(2)
        web2 = web.update_prediction(updated)
        assert make_prediction_id(1) not in web2.independence_groups[make_group_id(1)].member_predictions
        assert make_prediction_id(1) in web2.independence_groups[make_group_id(2)].member_predictions

    def test_nonexistent_raises(self, empty_web):
        with pytest.raises(BrokenReferenceError):
            empty_web.update_prediction(make_prediction(99))


# ── update_parameter ──────────────────────────────────────────────

class TestUpdateParameter:
    def test_value_change(self, web_with_params):
        old = web_with_params.parameters[make_parameter_id(1)]
        updated = copy.deepcopy(old)
        updated.value = 999.0
        web = web_with_params.update_parameter(updated)
        assert web.parameters[make_parameter_id(1)].value == 999.0

    def test_preserves_used_in_analyses(self, web_with_analysis):
        """used_in_analyses is a backlink — must survive update."""
        old = web_with_analysis.parameters[make_parameter_id(1)]
        assert make_analysis_id(1) in old.used_in_analyses
        updated = copy.deepcopy(old)
        updated.value = 0.0
        web = web_with_analysis.update_parameter(updated)
        assert make_analysis_id(1) in web.parameters[make_parameter_id(1)].used_in_analyses

    def test_nonexistent_raises(self, empty_web):
        with pytest.raises(BrokenReferenceError):
            empty_web.update_parameter(make_parameter(99))


# ── update_analysis ───────────────────────────────────────────────

class TestUpdateAnalysis:
    def test_uses_parameters_diff(self, web_with_params):
        web = web_with_params.register_analysis(
            make_analysis(1, uses_parameters={make_parameter_id(1)})
        )
        updated = copy.deepcopy(web.analyses[make_analysis_id(1)])
        updated.uses_parameters = {make_parameter_id(2)}
        web2 = web.update_analysis(updated)
        assert make_analysis_id(1) not in web2.parameters[make_parameter_id(1)].used_in_analyses
        assert make_analysis_id(1) in web2.parameters[make_parameter_id(2)].used_in_analyses

    def test_claims_covered_preserved(self, web_with_analysis):
        web = web_with_analysis.register_claim(
            make_claim(1, analyses={make_analysis_id(1)})
        )
        old = web.analyses[make_analysis_id(1)]
        assert make_claim_id(1) in old.claims_covered
        updated = copy.deepcopy(old)
        updated.notes = "updated notes"
        web2 = web.update_analysis(updated)
        assert make_claim_id(1) in web2.analyses[make_analysis_id(1)].claims_covered

    def test_nonexistent_raises(self, empty_web):
        with pytest.raises(BrokenReferenceError):
            empty_web.update_analysis(make_analysis(99))


# ── update_theory ─────────────────────────────────────────────────

class TestUpdateTheory:
    def test_basic(self, rich_web):
        old = rich_web.theories[make_theory_id(1)]
        updated = copy.deepcopy(old)
        updated.summary = "New summary"
        web = rich_web.update_theory(updated)
        assert web.theories[make_theory_id(1)].summary == "New summary"

    def test_broken_ref_raises(self, rich_web):
        old = rich_web.theories[make_theory_id(1)]
        updated = copy.deepcopy(old)
        updated.related_claims = {ClaimId("nonexistent")}
        with pytest.raises(BrokenReferenceError):
            rich_web.update_theory(updated)

    def test_nonexistent_raises(self, empty_web):
        with pytest.raises(BrokenReferenceError):
            empty_web.update_theory(make_theory(99))


# ── update_independence_group ─────────────────────────────────────

class TestUpdateIndependenceGroup:
    def test_preserves_member_predictions(self, rich_web):
        old = rich_web.independence_groups[make_group_id(1)]
        assert make_prediction_id(1) in old.member_predictions
        updated = copy.deepcopy(old)
        updated.notes = "note"
        web = rich_web.update_independence_group(updated)
        assert make_prediction_id(1) in web.independence_groups[make_group_id(1)].member_predictions

    def test_nonexistent_raises(self, empty_web):
        with pytest.raises(BrokenReferenceError):
            empty_web.update_independence_group(make_group(99))


# ── update_pairwise_separation ────────────────────────────────────

class TestUpdatePairwiseSeparation:
    def test_basis_change(self, empty_web):
        web = empty_web.register_independence_group(make_group(1))
        web = web.register_independence_group(make_group(2))
        web = web.add_pairwise_separation(make_separation(1))
        updated = copy.deepcopy(web.pairwise_separations[make_sep_id(1)])
        updated.basis = "new basis"
        web2 = web.update_pairwise_separation(updated)
        assert web2.pairwise_separations[make_sep_id(1)].basis == "new basis"

    def test_self_pair_rejected(self, empty_web):
        web = empty_web.register_independence_group(make_group(1))
        web = web.register_independence_group(make_group(2))
        web = web.add_pairwise_separation(make_separation(1))
        updated = copy.deepcopy(web.pairwise_separations[make_sep_id(1)])
        updated.group_a = make_group_id(1)
        updated.group_b = make_group_id(1)
        with pytest.raises(BrokenReferenceError, match="distinct"):
            web.update_pairwise_separation(updated)

    def test_nonexistent_raises(self, empty_web):
        with pytest.raises(BrokenReferenceError):
            empty_web.update_pairwise_separation(make_separation(99))


# ── update_discovery ──────────────────────────────────────────────

class TestUpdateDiscovery:
    def test_basic(self, rich_web):
        old = rich_web.discoveries[make_discovery_id(1)]
        updated = copy.deepcopy(old)
        updated.summary = "better summary"
        web = rich_web.update_discovery(updated)
        assert web.discoveries[make_discovery_id(1)].summary == "better summary"

    def test_nonexistent_raises(self, empty_web):
        with pytest.raises(BrokenReferenceError):
            empty_web.update_discovery(make_discovery(99))


# ── update_dead_end ───────────────────────────────────────────────

class TestUpdateDeadEnd:
    def test_basic(self, rich_web):
        old = rich_web.dead_ends[make_dead_end_id(1)]
        updated = copy.deepcopy(old)
        updated.description = "revised description"
        web = rich_web.update_dead_end(updated)
        assert web.dead_ends[make_dead_end_id(1)].description == "revised description"

    def test_nonexistent_raises(self, empty_web):
        with pytest.raises(BrokenReferenceError):
            empty_web.update_dead_end(make_dead_end(99))


# ── update_concept ────────────────────────────────────────────────

class TestUpdateConcept:
    def test_basic(self, rich_web):
        old = rich_web.concepts[make_concept_id(1)]
        updated = copy.deepcopy(old)
        updated.definition = "better def"
        web = rich_web.update_concept(updated)
        assert web.concepts[make_concept_id(1)].definition == "better def"

    def test_nonexistent_raises(self, empty_web):
        with pytest.raises(BrokenReferenceError):
            empty_web.update_concept(make_concept(99))
