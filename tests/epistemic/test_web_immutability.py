"""Tests for EpistemicWeb copy-on-write / immutability guarantees."""
from __future__ import annotations

import copy

import pytest

from horizon_research.epistemic.types import (
    ClaimStatus,
    PredictionStatus,
)
from horizon_research.epistemic.web import EpistemicWeb

from .conftest import (
    make_assumption,
    make_assumption_id,
    make_claim,
    make_claim_id,
    make_parameter,
    make_parameter_id,
    make_prediction,
    make_prediction_id,
)


class TestCopyOnWrite:
    """Every mutation returns a new web; the original is untouched."""

    def test_register_does_not_mutate_original(self, empty_web):
        web2 = empty_web.register_assumption(make_assumption(1))
        assert make_assumption_id(1) not in empty_web.assumptions
        assert make_assumption_id(1) in web2.assumptions

    def test_transition_does_not_mutate_original(self, rich_web):
        web2 = rich_web.transition_prediction(make_prediction_id(1), PredictionStatus.REFUTED)
        assert rich_web.predictions[make_prediction_id(1)].status == PredictionStatus.PENDING
        assert web2.predictions[make_prediction_id(1)].status == PredictionStatus.REFUTED

    def test_remove_does_not_mutate_original(self, rich_web):
        web2 = rich_web.remove_prediction(make_prediction_id(1))
        assert make_prediction_id(1) in rich_web.predictions
        assert make_prediction_id(1) not in web2.predictions

    def test_update_does_not_mutate_original(self, web_with_claim_chain):
        old = web_with_claim_chain.claims[make_claim_id(1)]
        updated = copy.deepcopy(old)
        updated.statement = "changed"
        web2 = web_with_claim_chain.update_claim(updated)
        assert web_with_claim_chain.claims[make_claim_id(1)].statement != "changed"
        assert web2.claims[make_claim_id(1)].statement == "changed"

    def test_chain_of_mutations_preserves_history(self, empty_web):
        """Each snapshot is independent."""
        w0 = empty_web
        w1 = w0.register_assumption(make_assumption(1))
        w2 = w1.register_assumption(make_assumption(2))
        assert len(w0.assumptions) == 0
        assert len(w1.assumptions) == 1
        assert len(w2.assumptions) == 2


class TestBidirectionalConsistency:
    """Backlink mutations on A must not leak into the original web."""

    def test_register_claim_backlinks_isolated(self, web_with_assumptions):
        web2 = web_with_assumptions.register_claim(
            make_claim(1, assumptions={make_assumption_id(1)})
        )
        # Original web's assumption should NOT have the new backlink
        assert make_claim_id(1) not in web_with_assumptions.assumptions[make_assumption_id(1)].used_in_claims
        assert make_claim_id(1) in web2.assumptions[make_assumption_id(1)].used_in_claims

    def test_register_prediction_backlinks_isolated(self, web_with_claim_chain):
        web2 = web_with_claim_chain.register_prediction(
            make_prediction(1, tests_assumptions={make_assumption_id(1)})
        )
        assert make_prediction_id(1) not in web_with_claim_chain.assumptions[make_assumption_id(1)].tested_by
        assert make_prediction_id(1) in web2.assumptions[make_assumption_id(1)].tested_by


class TestDeepCopyIsolation:
    """Mutating an entity stored in web A must not affect web B."""

    def test_entity_mutation_isolated(self, rich_web):
        """Directly mutating a claim object from web A doesn't affect web B."""
        web_b = rich_web.transition_claim(make_claim_id(1), ClaimStatus.REVISED)
        # Mutate the claim object from rich_web
        rich_web.claims[make_claim_id(1)].statement = "hacked"
        # web_b should be unaffected
        assert web_b.claims[make_claim_id(1)].statement != "hacked"
