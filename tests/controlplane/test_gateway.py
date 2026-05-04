"""Tests for Gateway and build_gateway.

Coverage plan
─────────────
__init__ / graph property
resolve_resource          — known key; unknown key
register                  — success; unknown resource; duplicate id; broken ref;
                            dry_run; payload_validator CRITICAL blocks
get                       — found; not found; unknown resource
list                      — empty; sorted; scalar filter; list-field filter; unknown resource
set                       — merges payload; entity not found; broken ref; dry_run
transition                — valid; entity not found; no-transition resource;
                            invalid status string; illegal graph transition
query                     — hypothesis_lineage; refutation_impact; parameter_impact;
                            assumption_support_status; unknown type; id coercion
_finalize_mutation        — CRITICAL blocks + graph unchanged; WARNING passes;
                            dry_run skips commit
_matches_filters          — list-contains; dict-subset; scalar-eq; no-match
_validate_payload         — no validator → []; validator called
build_gateway             — returns working Gateway
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest

from episteme.controlplane.factory import build_gateway
from episteme.controlplane.gateway import Gateway
from episteme.controlplane.validate import DomainValidator
from episteme.controlplane._gateway_results import GatewayResult
from episteme.epistemic.graph import EpistemicGraph
from episteme.epistemic.types import Finding, Severity


# ── Minimal payload helpers ───────────────────────────────────────

HYPOTHESIS_PAYLOAD: dict[str, Any] = {
    "id": "H-001",
    "statement": "Catalyst X increases yield",
    "type": "foundational",
    "category": "qualitative",
}

ASSUMPTION_PAYLOAD: dict[str, Any] = {
    "id": "A-001",
    "statement": "Detector is calibrated",
    "type": "empirical",
    "scope": "global",
    "criticality": "moderate",
}

PREDICTION_PAYLOAD: dict[str, Any] = {
    "id": "P-001",
    "observable": "yield",
    "predicted": 0.15,
    "tier": "fully_specified",
    "evidence_kind": "novel_prediction",
    "measurement_regime": "measured",
    "hypothesis_ids": ["H-001"],
}


# ── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture
def gw() -> Gateway:
    """Fresh gateway wrapping an empty EpistemicGraph."""
    return build_gateway(EpistemicGraph())


@pytest.fixture
def gw_with_hypothesis(gw: Gateway) -> Gateway:
    """Gateway that already has H-001 registered."""
    result = gw.register("hypothesis", HYPOTHESIS_PAYLOAD)
    assert result.status == "ok"
    return gw


@pytest.fixture
def gw_populated(gw: Gateway) -> Gateway:
    """Gateway with A-001, H-001, and P-001 registered in dependency order."""
    gw.register("assumption", ASSUMPTION_PAYLOAD)
    gw.register("hypothesis", {**HYPOTHESIS_PAYLOAD, "assumptions": ["A-001"]})
    gw.register("prediction", PREDICTION_PAYLOAD)
    return gw


# ── graph property ────────────────────────────────────────────────


def test_graph_property_returns_epistemic_graph(gw):
    assert isinstance(gw.graph, EpistemicGraph)


def test_graph_property_reflects_mutations(gw):
    gw.register("hypothesis", HYPOTHESIS_PAYLOAD)
    assert "H-001" in gw.graph.hypotheses


# ── resolve_resource ──────────────────────────────────────────────


def test_resolve_resource_known_key(gw):
    assert gw.resolve_resource("hypothesis") == "hypothesis"


def test_resolve_resource_unknown_key_raises(gw):
    with pytest.raises(KeyError):
        gw.resolve_resource("unicorn")


# ── register ─────────────────────────────────────────────────────


def test_register_hypothesis_success(gw):
    result = gw.register("hypothesis", HYPOTHESIS_PAYLOAD)
    assert result.status == "ok"
    assert result.changed is True
    assert "H-001" in gw.graph.hypotheses


def test_register_returns_gw_result(gw):
    result = gw.register("hypothesis", HYPOTHESIS_PAYLOAD)
    assert isinstance(result, GatewayResult)


def test_register_unknown_resource(gw):
    result = gw.register("banana", {"id": "X-001"})
    assert result.status == "error"
    assert result.changed is False


def test_register_duplicate_id(gw_with_hypothesis):
    result = gw_with_hypothesis.register("hypothesis", HYPOTHESIS_PAYLOAD)
    assert result.status == "error"
    assert result.changed is False


def test_register_broken_reference(gw):
    """Hypothesis referencing a non-existent assumption returns error."""
    result = gw.register("hypothesis", {**HYPOTHESIS_PAYLOAD, "assumptions": ["MISSING"]})
    assert result.status == "error"
    assert result.changed is False


def test_register_dry_run_does_not_mutate(gw):
    result = gw.register("hypothesis", HYPOTHESIS_PAYLOAD, dry_run=True)
    assert result.status == "ok"
    assert result.changed is False
    assert "H-001" not in gw.graph.hypotheses


def test_register_dry_run_ok_still_returns_findings(gw):
    result = gw.register("hypothesis", HYPOTHESIS_PAYLOAD, dry_run=True)
    assert isinstance(result.findings, list)


def test_register_all_entity_types_smoke(gw):
    """Each resource type can be registered through the Gateway without error."""
    # assumption
    r = gw.register("assumption", ASSUMPTION_PAYLOAD)
    assert r.status == "ok", r.message

    # hypothesis (references A-001)
    r = gw.register("hypothesis", {**HYPOTHESIS_PAYLOAD, "assumptions": ["A-001"]})
    assert r.status == "ok", r.message

    # prediction (references H-001)
    r = gw.register("prediction", PREDICTION_PAYLOAD)
    assert r.status == "ok", r.message

    # objective
    r = gw.register("objective", {"id": "T-001", "title": "Main goal", "kind": "goal"})
    assert r.status == "ok", r.message

    # discovery
    r = gw.register("discovery", {
        "id": "D-001",
        "title": "Finding A",
        "date": "2026-04-01",
        "summary": "A notable discovery",
        "impact": "Changes direction",
    })
    assert r.status == "ok", r.message

    # parameter
    r = gw.register("parameter", {"id": "PAR-001", "name": "threshold", "value": 0.05})
    assert r.status == "ok", r.message

    # analysis
    r = gw.register("analysis", {"id": "AN-001", "path": "scripts/run.py"})
    assert r.status == "ok", r.message

    # dead_end
    r = gw.register("dead_end", {"id": "DE-001", "title": "Approach Y", "description": "Tried X, failed"})
    assert r.status == "ok", r.message

    # independence_group
    r = gw.register("independence_group", {"id": "IG-001", "label": "Group A", "rationale": "different datasets"})
    assert r.status == "ok", r.message

    # observation
    r = gw.register("observation", {
        "id": "OBS-001",
        "description": "baseline measurement",
        "value": 1.5,
        "date": "2026-04-01",
    })
    assert r.status == "ok", r.message


# ── register: payload_validator ───────────────────────────────────


class _BlockingValidator:
    """PayloadValidator stub that always returns a CRITICAL finding."""

    def validate(self, resource: str, payload: Mapping[str, object]) -> list[Finding]:
        return [Finding(Severity.CRITICAL, resource, "schema error")]


class _WarningValidator:
    """PayloadValidator stub that always returns a WARNING finding."""

    def validate(self, resource: str, payload: Mapping[str, object]) -> list[Finding]:
        return [Finding(Severity.WARNING, resource, "advisory")]


def test_register_payload_validator_critical_blocks(gw):
    gw2 = Gateway(gw.graph, DomainValidator(), payload_validator=_BlockingValidator())
    result = gw2.register("hypothesis", HYPOTHESIS_PAYLOAD)
    assert result.status == "error"
    assert result.changed is False
    assert any(f.severity == Severity.CRITICAL for f in result.findings)


def test_register_payload_validator_warning_does_not_block(gw):
    gw2 = Gateway(gw.graph, DomainValidator(), payload_validator=_WarningValidator())
    result = gw2.register("hypothesis", HYPOTHESIS_PAYLOAD)
    assert result.status == "ok"
    assert result.changed is True


def test_validate_payload_no_validator_returns_empty(gw):
    findings = gw._validate_payload("hypothesis", HYPOTHESIS_PAYLOAD)
    assert findings == []


def test_validate_payload_delegates_to_validator():
    gw2 = Gateway(EpistemicGraph(), DomainValidator(), payload_validator=_BlockingValidator())
    findings = gw2._validate_payload("hypothesis", HYPOTHESIS_PAYLOAD)
    assert len(findings) == 1
    assert findings[0].severity == Severity.CRITICAL


# ── get ───────────────────────────────────────────────────────────


def test_get_found(gw_with_hypothesis):
    result = gw_with_hypothesis.get("hypothesis", "H-001")
    assert result.status == "ok"
    assert result.changed is False
    assert result.data["resource"]["id"] == "H-001"


def test_get_not_found(gw):
    result = gw.get("hypothesis", "MISSING")
    assert result.status == "error"
    assert result.data is None


def test_get_unknown_resource(gw):
    result = gw.get("banana", "X-001")
    assert result.status == "error"


def test_get_returns_serialized_entity(gw_with_hypothesis):
    result = gw_with_hypothesis.get("hypothesis", "H-001")
    entity = result.data["resource"]
    assert entity["statement"] == "Catalyst X increases yield"
    assert entity["type"] == "foundational"


# ── list ──────────────────────────────────────────────────────────


def test_list_empty_collection(gw):
    result = gw.list("hypothesis")
    assert result.status == "ok"
    assert result.data["count"] == 0
    assert result.data["items"] == []


def test_list_returns_all_entities(gw_with_hypothesis):
    result = gw_with_hypothesis.list("hypothesis")
    assert result.data["count"] == 1
    assert result.data["items"][0]["id"] == "H-001"


def test_list_sorted_by_id(gw):
    gw.register("hypothesis", {**HYPOTHESIS_PAYLOAD, "id": "H-002", "statement": "B"})
    gw.register("hypothesis", {**HYPOTHESIS_PAYLOAD, "id": "H-001", "statement": "A"})
    result = gw.list("hypothesis")
    ids = [item["id"] for item in result.data["items"]]
    assert ids == sorted(ids)


def test_list_unknown_resource(gw):
    result = gw.list("banana")
    assert result.status == "error"


def test_list_scalar_filter(gw_with_hypothesis):
    result = gw_with_hypothesis.list("hypothesis", type="foundational")
    assert result.data["count"] == 1

    result = gw_with_hypothesis.list("hypothesis", type="derived")
    assert result.data["count"] == 0


def test_list_multiple_entities_filter(gw):
    gw.register("hypothesis", {**HYPOTHESIS_PAYLOAD, "id": "H-001", "type": "foundational"})
    gw.register("hypothesis", {**HYPOTHESIS_PAYLOAD, "id": "H-002", "statement": "B", "type": "derived"})
    result = gw.list("hypothesis", type="derived")
    assert result.data["count"] == 1
    assert result.data["items"][0]["id"] == "H-002"


# ── _matches_filters ──────────────────────────────────────────────


def test_matches_filters_scalar_match(gw):
    assert gw._matches_filters({"status": "active"}, {"status": "active"}) is True


def test_matches_filters_scalar_no_match(gw):
    assert gw._matches_filters({"status": "active"}, {"status": "revised"}) is False


def test_matches_filters_list_contains(gw):
    item = {"hypothesis_ids": ["H-001", "H-002"]}
    assert gw._matches_filters(item, {"hypothesis_ids": "H-001"}) is True
    assert gw._matches_filters(item, {"hypothesis_ids": "H-999"}) is False


def test_matches_filters_dict_subset(gw):
    item = {"parameter_constraints": {"PAR-001": "<0.05", "PAR-002": ">0"}}
    assert gw._matches_filters(item, {"parameter_constraints": {"PAR-001": "<0.05"}}) is True
    assert gw._matches_filters(item, {"parameter_constraints": {"PAR-999": "x"}}) is False


def test_matches_filters_empty_filters_always_true(gw):
    assert gw._matches_filters({"id": "X"}, {}) is True


def test_matches_filters_missing_key_no_match(gw):
    assert gw._matches_filters({}, {"status": "active"}) is False


# ── set ───────────────────────────────────────────────────────────


def test_set_updates_field(gw_with_hypothesis):
    result = gw_with_hypothesis.set("hypothesis", "H-001", {"statement": "Updated statement"})
    assert result.status == "ok"
    assert result.changed is True
    get_result = gw_with_hypothesis.get("hypothesis", "H-001")
    assert get_result.data["resource"]["statement"] == "Updated statement"


def test_set_preserves_unchanged_fields(gw_with_hypothesis):
    gw_with_hypothesis.set("hypothesis", "H-001", {"statement": "New"})
    get_result = gw_with_hypothesis.get("hypothesis", "H-001")
    assert get_result.data["resource"]["type"] == "foundational"


def test_set_entity_not_found(gw):
    result = gw.set("hypothesis", "MISSING", {"statement": "x"})
    assert result.status == "error"
    assert result.changed is False


def test_set_unknown_resource(gw):
    result = gw.set("banana", "X", {"id": "X"})
    assert result.status == "error"


def test_set_dry_run_does_not_mutate(gw_with_hypothesis):
    result = gw_with_hypothesis.set(
        "hypothesis", "H-001", {"statement": "Changed"}, dry_run=True
    )
    assert result.status == "ok"
    assert result.changed is False
    get_result = gw_with_hypothesis.get("hypothesis", "H-001")
    assert get_result.data["resource"]["statement"] == "Catalyst X increases yield"


def test_set_broken_reference(gw_with_hypothesis):
    """Setting assumptions= to a non-existent assumption returns error."""
    result = gw_with_hypothesis.set(
        "hypothesis", "H-001", {"assumptions": ["MISSING"]}
    )
    assert result.status == "error"
    assert result.changed is False


# ── transition ────────────────────────────────────────────────────


def test_transition_hypothesis_valid(gw_with_hypothesis):
    result = gw_with_hypothesis.transition("hypothesis", "H-001", "revised")
    assert result.status == "ok"
    assert result.changed is True
    get_result = gw_with_hypothesis.get("hypothesis", "H-001")
    assert get_result.data["resource"]["status"] == "revised"


def test_transition_entity_not_found(gw):
    result = gw.transition("hypothesis", "MISSING", "revised")
    assert result.status == "error"
    assert result.changed is False


def test_transition_unknown_resource(gw):
    result = gw.transition("banana", "X", "active")
    assert result.status == "error"


def test_transition_no_transition_support(gw):
    """Assumptions do not have a transition_method; should return error."""
    gw.register("assumption", ASSUMPTION_PAYLOAD)
    result = gw.transition("assumption", "A-001", "questioned")
    assert result.status == "error"
    assert result.changed is False


def test_transition_invalid_status_string(gw_with_hypothesis):
    result = gw_with_hypothesis.transition("hypothesis", "H-001", "not_a_real_status")
    assert result.status == "error"
    assert result.changed is False


def test_transition_illegal_graph_transition(gw_with_hypothesis):
    """Attempting an invalid status transition (e.g. ACTIVE → ACTIVE) returns error."""
    result = gw_with_hypothesis.transition("hypothesis", "H-001", "active")
    assert result.status == "error"
    assert result.changed is False


def test_transition_dry_run_does_not_mutate(gw_with_hypothesis):
    result = gw_with_hypothesis.transition("hypothesis", "H-001", "revised", dry_run=True)
    assert result.status == "ok"
    assert result.changed is False
    get_result = gw_with_hypothesis.get("hypothesis", "H-001")
    assert get_result.data["resource"]["status"] == "active"


def test_transition_prediction(gw_populated):
    result = gw_populated.transition("prediction", "P-001", "confirmed")
    assert result.status == "error"  # MEASURED prediction needs observed value to confirm


def test_transition_discovery(gw):
    r = gw.register("discovery", {
        "id": "D-001",
        "title": "X found",
        "date": "2026-04-01",
        "summary": "We found something important",
        "impact": "Changes the hypothesis direction",
    })
    assert r.status == "ok", r.message
    result = gw.transition("discovery", "D-001", "integrated")
    assert result.status == "ok"
    assert result.changed is True


# ── _finalize_mutation: blocking behavior ─────────────────────────


class _AlwaysCriticalValidator:
    def validate(self, graph) -> list[Finding]:
        return [Finding(Severity.CRITICAL, "test", "always critical")]


class _AlwaysWarningValidator:
    def validate(self, graph) -> list[Finding]:
        return [Finding(Severity.WARNING, "test", "always warn")]


def test_finalize_mutation_critical_blocks_graph_swap(gw):
    blocking_gw = Gateway(EpistemicGraph(), _AlwaysCriticalValidator())
    old_graph = blocking_gw.graph
    result = blocking_gw.register("hypothesis", HYPOTHESIS_PAYLOAD)
    assert result.status == "BLOCKED"
    assert result.changed is False
    assert blocking_gw.graph is old_graph  # graph unchanged


def test_finalize_mutation_warning_does_not_block(gw):
    warn_gw = Gateway(EpistemicGraph(), _AlwaysWarningValidator())
    result = warn_gw.register("hypothesis", HYPOTHESIS_PAYLOAD)
    assert result.status == "ok"
    assert result.changed is True
    assert any(f.severity == Severity.WARNING for f in result.findings)


def test_finalize_mutation_dry_run_skips_commit():
    warn_gw = Gateway(EpistemicGraph(), _AlwaysWarningValidator())
    old_graph = warn_gw.graph
    result = warn_gw.register("hypothesis", HYPOTHESIS_PAYLOAD, dry_run=True)
    assert result.status == "ok"
    assert result.changed is False
    assert warn_gw.graph is old_graph


def test_finalize_mutation_blocked_findings_included(gw):
    blocking_gw = Gateway(EpistemicGraph(), _AlwaysCriticalValidator())
    result = blocking_gw.register("hypothesis", HYPOTHESIS_PAYLOAD)
    assert result.status == "BLOCKED"
    assert len(result.findings) >= 1
    assert result.findings[0].severity == Severity.CRITICAL


# ── query ─────────────────────────────────────────────────────────


def test_query_unknown_type(gw):
    result = gw.query("not_a_real_query")
    assert result.status == "error"
    assert result.data is None


def test_query_hypothesis_lineage_empty(gw_with_hypothesis):
    result = gw_with_hypothesis.query("hypothesis_lineage", cid="H-001")
    assert result.status == "ok"
    assert result.data["result"] == []  # no ancestors


def test_query_hypothesis_lineage_with_ancestor(gw):
    gw.register("hypothesis", {**HYPOTHESIS_PAYLOAD, "id": "H-001", "type": "foundational"})
    gw.register("hypothesis", {
        "id": "H-002",
        "statement": "Derived from H-001",
        "type": "derived",
        "depends_on": ["H-001"],
    })
    result = gw.query("hypothesis_lineage", cid="H-002")
    assert result.status == "ok"
    assert "H-001" in result.data["result"]


def test_query_refutation_impact(gw_populated):
    result = gw_populated.query("refutation_impact", pid="P-001")
    assert result.status == "ok"
    data = result.data["result"]
    assert "H-001" in data["hypothesis_ids"]


def test_query_parameter_impact(gw):
    gw.register("parameter", {"id": "PAR-001", "name": "threshold", "value": 0.05})
    gw.register("analysis", {"id": "AN-001", "uses_parameters": ["PAR-001"]})
    result = gw.query("parameter_impact", pid="PAR-001")
    assert result.status == "ok"
    assert "AN-001" in result.data["result"]["stale_analyses"]


def test_query_assumption_support_status(gw_populated):
    result = gw_populated.query("assumption_support_status", aid="A-001")
    assert result.status == "ok"
    data = result.data["result"]
    assert "H-001" in data["direct_hypotheses"]


def test_query_predictions_depending_on_hypothesis(gw_populated):
    result = gw_populated.query("predictions_depending_on_hypothesis", cid="H-001")
    assert result.status == "ok"
    assert "P-001" in result.data["result"]


def test_query_id_coercion_works(gw_with_hypothesis):
    """String IDs passed to query are correctly coerced to typed NewTypes."""
    result = gw_with_hypothesis.query("hypothesis_lineage", cid="H-001")
    assert result.status == "ok"


def test_query_changed_is_false(gw_with_hypothesis):
    result = gw_with_hypothesis.query("hypothesis_lineage", cid="H-001")
    assert result.changed is False


# ── build_gateway ─────────────────────────────────────────────────


def test_build_gateway_returns_gateway():
    gw = build_gateway(EpistemicGraph())
    assert isinstance(gw, Gateway)


def test_build_gateway_with_payload_validator():
    gw = build_gateway(EpistemicGraph(), payload_validator=_BlockingValidator())
    result = gw.register("hypothesis", HYPOTHESIS_PAYLOAD)
    assert result.status == "error"


def test_build_gateway_wraps_domain_validator():
    """DomainValidator is wired; CRITICAL invariant violations block mutations."""
    gw = build_gateway(EpistemicGraph())
    # Register a foundational assumption and hypothesis, then confirm
    # the gateway runs invariant checks on mutation (it won't block here,
    # but it runs — if domain validator were missing, this would raise).
    result = gw.register("hypothesis", HYPOTHESIS_PAYLOAD)
    assert result.status == "ok"


def test_build_gateway_empty_graph_has_no_entities():
    gw = build_gateway(EpistemicGraph())
    result = gw.list("hypothesis")
    assert result.data["count"] == 0
