"""Tests for JsonRepository.

Coverage:
- load on missing file returns empty graph
- save creates parent directories
- save/load round-trip: version preserved
- save/load round-trip: entities preserved (id, scalar fields)
- save/load round-trip: set fields preserved (assumptions on hypothesis)
- save/load round-trip: backlink fields preserved (assumption.used_in_hypotheses)
- save/load round-trip: empty collections
- save is atomic (uses .tmp file then os.replace)
- load: unknown/extra JSON keys are ignored gracefully
- base_graph full round-trip (multi-entity, cross-references)
- save: version is incremented? (no — JsonRepository does not increment; graph owns version)
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from episteme.adapters.json_repository import JsonRepository
from episteme.epistemic.graph import EpistemicGraph
from episteme.epistemic.model import (
    Assumption,
    AssumptionId,
    AssumptionType,
    Hypothesis,
    HypothesisId,
    HypothesisType,
)
from episteme.epistemic.types import Criticality


# ── Helpers ───────────────────────────────────────────────────────


def _minimal_graph() -> EpistemicGraph:
    """EpistemicGraph with a single assumption and hypothesis."""
    g = EpistemicGraph()
    g = g.register_assumption(
        Assumption(
            id=AssumptionId("A-001"),
            statement="Detector calibrated",
            type=AssumptionType.EMPIRICAL,
            scope="global",
            criticality=Criticality.LOAD_BEARING,
        )
    )
    g = g.register_hypothesis(
        Hypothesis(
            id=HypothesisId("H-001"),
            statement="Catalyst X increases yield",
            type=HypothesisType.FOUNDATIONAL,
            assumptions={AssumptionId("A-001")},
        )
    )
    return g


# ── load: missing file ────────────────────────────────────────────


def test_load_missing_file_returns_empty_graph(tmp_path):
    repo = JsonRepository(tmp_path / "graph.json")
    graph = repo.load()
    assert isinstance(graph, EpistemicGraph)
    assert graph.version == 0
    assert len(graph.hypotheses) == 0


# ── save: directory creation ──────────────────────────────────────


def test_save_creates_parent_directories(tmp_path):
    nested = tmp_path / "a" / "b" / "c" / "graph.json"
    repo = JsonRepository(nested)
    repo.save(EpistemicGraph())
    assert nested.exists()


# ── save/load: version ────────────────────────────────────────────


def test_round_trip_preserves_version(tmp_path):
    path = tmp_path / "graph.json"
    original = EpistemicGraph(version=7)
    JsonRepository(path).save(original)
    loaded = JsonRepository(path).load()
    assert loaded.version == 7


# ── save/load: entities ───────────────────────────────────────────


def test_round_trip_preserves_hypothesis_scalar_fields(tmp_path):
    path = tmp_path / "graph.json"
    g = EpistemicGraph()
    g = g.register_hypothesis(
        Hypothesis(
            id=HypothesisId("H-001"),
            statement="Yield baseline",
            type=HypothesisType.FOUNDATIONAL,
            scope="lab",
            refutation_criteria="Show yield unchanged",
            notes="important",
        )
    )
    JsonRepository(path).save(g)
    loaded = JsonRepository(path).load()
    h = loaded.hypotheses[HypothesisId("H-001")]
    assert h.statement == "Yield baseline"
    assert h.scope == "lab"
    assert h.refutation_criteria == "Show yield unchanged"
    assert h.notes == "important"


def test_round_trip_preserves_hypothesis_set_fields(tmp_path):
    path = tmp_path / "graph.json"
    g = _minimal_graph()
    JsonRepository(path).save(g)
    loaded = JsonRepository(path).load()
    h = loaded.hypotheses[HypothesisId("H-001")]
    assert AssumptionId("A-001") in h.assumptions


def test_round_trip_preserves_assumption_count(tmp_path):
    path = tmp_path / "graph.json"
    g = _minimal_graph()
    JsonRepository(path).save(g)
    loaded = JsonRepository(path).load()
    assert len(loaded.assumptions) == 1
    assert AssumptionId("A-001") in loaded.assumptions


# ── save/load: backlinks ──────────────────────────────────────────


def test_round_trip_preserves_backlinks(tmp_path):
    """assumption.used_in_hypotheses backlink is restored by direct construction."""
    path = tmp_path / "graph.json"
    g = _minimal_graph()
    # After registering H-001 (which refs A-001), the graph sets the backlink.
    assert HypothesisId("H-001") in g.assumptions[AssumptionId("A-001")].used_in_hypotheses

    JsonRepository(path).save(g)
    loaded = JsonRepository(path).load()
    assert HypothesisId("H-001") in loaded.assumptions[AssumptionId("A-001")].used_in_hypotheses


# ── save/load: empty collections ─────────────────────────────────


def test_round_trip_empty_graph(tmp_path):
    path = tmp_path / "graph.json"
    JsonRepository(path).save(EpistemicGraph())
    loaded = JsonRepository(path).load()
    assert len(loaded.hypotheses) == 0
    assert len(loaded.assumptions) == 0
    assert len(loaded.predictions) == 0


def test_round_trip_all_collections_present_in_json(tmp_path):
    path = tmp_path / "graph.json"
    JsonRepository(path).save(EpistemicGraph())
    raw = json.loads(path.read_text())
    expected_keys = {
        "version", "hypotheses", "assumptions", "predictions", "objectives",
        "discoveries", "analyses", "independence_groups", "pairwise_separations",
        "dead_ends", "parameters", "observations", "experiments",
    }
    assert expected_keys.issubset(raw.keys())


# ── save: atomicity ───────────────────────────────────────────────


def test_save_does_not_leave_tmp_file(tmp_path):
    path = tmp_path / "graph.json"
    JsonRepository(path).save(EpistemicGraph())
    tmp = path.with_suffix(".tmp")
    assert not tmp.exists()


def test_save_overwrites_existing_file(tmp_path):
    path = tmp_path / "graph.json"
    repo = JsonRepository(path)
    g1 = EpistemicGraph(version=1)
    g2 = EpistemicGraph(version=2)
    repo.save(g1)
    repo.save(g2)
    loaded = repo.load()
    assert loaded.version == 2


# ── load: extra JSON keys are ignored ────────────────────────────


def test_load_ignores_unknown_top_level_keys(tmp_path):
    path = tmp_path / "graph.json"
    data = {
        "version": 3,
        "hypotheses": [],
        "assumptions": [],
        "predictions": [],
        "objectives": [],
        "discoveries": [],
        "analyses": [],
        "independence_groups": [],
        "pairwise_separations": [],
        "dead_ends": [],
        "parameters": [],
        "observations": [],
        "experiments": [],
        "_schema_version": "v2",  # unknown key — should not raise
    }
    path.write_text(json.dumps(data))
    loaded = JsonRepository(path).load()
    assert loaded.version == 3


# ── full round-trip via base_graph fixture ────────────────────────


def test_base_graph_full_round_trip(tmp_path, base_graph):
    """The shared base_graph fixture survives a save/load cycle intact."""
    path = tmp_path / "graph.json"
    JsonRepository(path).save(base_graph)
    loaded = JsonRepository(path).load()

    # Entity counts match
    assert len(loaded.hypotheses) == len(base_graph.hypotheses)
    assert len(loaded.assumptions) == len(base_graph.assumptions)
    assert len(loaded.predictions) == len(base_graph.predictions)
    assert len(loaded.observations) == len(base_graph.observations)

    # Spot-check a hypothesis statement
    for cid, hyp in base_graph.hypotheses.items():
        assert loaded.hypotheses[cid].statement == hyp.statement

    # Spot-check assumption backlinks
    for aid, assm in base_graph.assumptions.items():
        assert loaded.assumptions[aid].used_in_hypotheses == assm.used_in_hypotheses


# ── supports_native_validation ────────────────────────────────────


def test_supports_native_validation_is_false(tmp_path):
    repo = JsonRepository(tmp_path / "g.json")
    assert repo.supports_native_validation is False
