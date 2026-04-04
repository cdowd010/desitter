"""Tests for EpistemicWeb transition methods."""
from __future__ import annotations

import pytest

from horizon_research.epistemic.types import (
    ClaimStatus,
    DeadEndStatus,
    DiscoveryStatus,
    PredictionStatus,
    TheoryStatus,
)
from horizon_research.epistemic.web import BrokenReferenceError

from .conftest import (
    make_claim_id,
    make_dead_end_id,
    make_discovery_id,
    make_prediction_id,
    make_theory_id,
)


class TestTransitionPrediction:
    def test_happy_path(self, rich_web):
        web = rich_web.transition_prediction(make_prediction_id(1), PredictionStatus.CONFIRMED)
        assert web.predictions[make_prediction_id(1)].status == PredictionStatus.CONFIRMED

    def test_to_refuted(self, rich_web):
        web = rich_web.transition_prediction(make_prediction_id(1), PredictionStatus.REFUTED)
        assert web.predictions[make_prediction_id(1)].status == PredictionStatus.REFUTED

    def test_nonexistent_raises(self, empty_web):
        with pytest.raises(BrokenReferenceError):
            empty_web.transition_prediction("P-999", PredictionStatus.CONFIRMED)


class TestTransitionClaim:
    def test_to_retracted(self, rich_web):
        web = rich_web.transition_claim(make_claim_id(1), ClaimStatus.RETRACTED)
        assert web.claims[make_claim_id(1)].status == ClaimStatus.RETRACTED

    def test_to_revised(self, rich_web):
        web = rich_web.transition_claim(make_claim_id(1), ClaimStatus.REVISED)
        assert web.claims[make_claim_id(1)].status == ClaimStatus.REVISED

    def test_nonexistent_raises(self, empty_web):
        with pytest.raises(BrokenReferenceError):
            empty_web.transition_claim("C-999", ClaimStatus.RETRACTED)


class TestTransitionTheory:
    def test_to_abandoned(self, rich_web):
        web = rich_web.transition_theory(make_theory_id(1), TheoryStatus.ABANDONED)
        assert web.theories[make_theory_id(1)].status == TheoryStatus.ABANDONED

    def test_nonexistent_raises(self, empty_web):
        with pytest.raises(BrokenReferenceError):
            empty_web.transition_theory("T-999", TheoryStatus.REFINED)


class TestTransitionDeadEnd:
    def test_to_resolved(self, rich_web):
        web = rich_web.transition_dead_end(make_dead_end_id(1), DeadEndStatus.RESOLVED)
        assert web.dead_ends[make_dead_end_id(1)].status == DeadEndStatus.RESOLVED

    def test_nonexistent_raises(self, empty_web):
        with pytest.raises(BrokenReferenceError):
            empty_web.transition_dead_end("DE-999", DeadEndStatus.ARCHIVED)


class TestTransitionDiscovery:
    def test_to_integrated(self, rich_web):
        web = rich_web.transition_discovery(make_discovery_id(1), DiscoveryStatus.INTEGRATED)
        assert web.discoveries[make_discovery_id(1)].status == DiscoveryStatus.INTEGRATED

    def test_nonexistent_raises(self, empty_web):
        with pytest.raises(BrokenReferenceError):
            empty_web.transition_discovery("D-999", DiscoveryStatus.ARCHIVED)
