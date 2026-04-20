"""Tests for EpistemicGraph mutation operations."""
from __future__ import annotations

from episteme.epistemic.model import (
    ClaimId,
    ObservationId,
    PredictionId,
    TheoryId,
)


def test_theory_claim_bidirectional_links(base_graph):
    """Registering a Claim with theories= auto-populates Theory.motivates_claims."""
    assert ClaimId("C-001") in base_graph.theories[TheoryId("T-001")].motivates_claims
    assert TheoryId("T-001") in base_graph.claims[ClaimId("C-001")].theories


def test_prediction_stress_criteria_stored(base_graph):
    """stress_criteria field is persisted on the Prediction."""
    p = base_graph.predictions[PredictionId("P-001")]
    assert p.stress_criteria == "Yield increase <10% but >5% would be stressed"


def test_standalone_observation(base_graph):
    """Observations can exist without linking to any prediction."""
    obs = base_graph.observations[ObservationId("OBS-001")]
    assert obs.predictions == set()


def test_observation_prediction_bidirectional(base_graph):
    """Registering an observation with predictions= auto-populates Prediction.observations."""
    assert ObservationId("OBS-002") in base_graph.predictions[PredictionId("P-001")].observations


def test_theory_removal_scrubs_claim_theories(base_graph):
    """Removing a Theory clears its id from all Claim.theories sets."""
    graph = base_graph.remove_prediction(PredictionId("P-001"))
    graph = graph.remove_claim(ClaimId("C-001"))
    graph = graph.remove_theory(TheoryId("T-001"))
    assert TheoryId("T-001") not in graph.theories


def test_observation_removal_cleans_prediction_backlink(base_graph):
    """Removing an Observation tears down its Prediction.observations backlink."""
    graph = base_graph.remove_observation(ObservationId("OBS-002"))
    assert ObservationId("OBS-002") not in graph.predictions[PredictionId("P-001")].observations
