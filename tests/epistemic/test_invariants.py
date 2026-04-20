"""Tests for on-demand semantic invariant validators."""
from __future__ import annotations

from episteme.epistemic.model import ObjectiveId, ObjectiveStatus
from episteme.epistemic.invariants import validate_all


def test_objective_abandonment_impact(base_graph):
    """Claims whose only motivating objective is ABANDONED should trigger a warning."""
    graph = base_graph.transition_objective(ObjectiveId("T-001"), ObjectiveStatus.ABANDONED)
    findings = validate_all(graph)
    assert any("theoretical motivation" in f.message for f in findings)


def test_load_bearing_assumption_untested(base_graph):
    """LOAD_BEARING assumptions with no tested_by links should trigger a critical finding."""
    findings = validate_all(base_graph)
    assert any("LOAD_BEARING" in f.message for f in findings)
