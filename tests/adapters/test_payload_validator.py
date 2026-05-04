"""Tests for SchemaPayloadValidator.

Coverage:
- unknown resource → single CRITICAL finding
- hypothesis: all required fields present → empty list
- hypothesis: missing required field (id) → CRITICAL
- hypothesis: missing required field (statement) → CRITICAL
- hypothesis: missing both required fields → two CRITICALs
- optional fields absent → no finding
- assumption: required field (statement) present → passes
- assumption: missing required field → CRITICAL
- prediction: missing both required fields (id, observable, predicted, tier...) detected
- findings use CRITICAL severity
- source path format: "payload/<resource>/<field>"
- unknown resource source path: "payload/<resource>"
"""
from __future__ import annotations

import pytest

from episteme.adapters.payload_validator import SchemaPayloadValidator
from episteme.epistemic.types import Severity


@pytest.fixture
def validator() -> SchemaPayloadValidator:
    return SchemaPayloadValidator()


# ── unknown resource ──────────────────────────────────────────────


def test_unknown_resource_returns_critical_finding(validator):
    findings = validator.validate("not_a_resource", {"id": "X-001"})
    assert len(findings) == 1
    assert findings[0].severity is Severity.CRITICAL
    assert "not_a_resource" in findings[0].message


def test_unknown_resource_source_path(validator):
    findings = validator.validate("unicorn", {})
    assert findings[0].source == "payload/unicorn"


# ── hypothesis: required fields ───────────────────────────────────


def test_hypothesis_all_required_fields_present(validator):
    findings = validator.validate("hypothesis", {"id": "H-001", "statement": "S"})
    assert findings == []


def test_hypothesis_missing_id_is_critical(validator):
    findings = validator.validate("hypothesis", {"statement": "S"})
    messages = [f.message for f in findings]
    assert any("id" in m for m in messages)
    assert all(f.severity is Severity.CRITICAL for f in findings)


def test_hypothesis_missing_statement_is_critical(validator):
    findings = validator.validate("hypothesis", {"id": "H-001"})
    messages = [f.message for f in findings]
    assert any("statement" in m for m in messages)


def test_hypothesis_missing_both_required_fields(validator):
    findings = validator.validate("hypothesis", {})
    field_names = {f.source.rsplit("/", 1)[-1] for f in findings}
    assert "id" in field_names
    assert "statement" in field_names


def test_hypothesis_optional_fields_absent_no_finding(validator):
    """Fields with defaults (scope, notes, tags, …) must not produce findings."""
    findings = validator.validate("hypothesis", {"id": "H-001", "statement": "S"})
    assert findings == []


# ── source path format ────────────────────────────────────────────


def test_finding_source_includes_field_name(validator):
    findings = validator.validate("hypothesis", {"id": "H-001"})
    sources = {f.source for f in findings}
    assert "payload/hypothesis/statement" in sources


# ── assumption ────────────────────────────────────────────────────


def test_assumption_missing_statement_is_critical(validator):
    findings = validator.validate("assumption", {"id": "A-001"})
    assert any("statement" in f.source for f in findings)


def test_assumption_all_required_fields_present(validator):
    findings = validator.validate("assumption", {"id": "A-001", "statement": "X", "type": "empirical"})
    assert findings == []


# ── prediction ────────────────────────────────────────────────────


def test_prediction_missing_required_fields(validator):
    """Prediction has id, observable, predicted, tier, evidence_kind, measurement_regime as required."""
    findings = validator.validate("prediction", {})
    field_names = {f.source.rsplit("/", 1)[-1] for f in findings}
    # id and observable are certain to be required
    assert "id" in field_names
    assert "observable" in field_names


def test_prediction_minimal_valid_payload(validator):
    findings = validator.validate("prediction", {
        "id": "P-001",
        "observable": "yield",
        "predicted": 0.5,
        "tier": "fully_specified",
        "evidence_kind": "novel_prediction",
        "measurement_regime": "measured",
        "hypothesis_ids": ["H-001"],
    })
    assert findings == []


# ── all findings are CRITICAL ─────────────────────────────────────


def test_all_missing_field_findings_are_critical(validator):
    findings = validator.validate("hypothesis", {})
    assert all(f.severity is Severity.CRITICAL for f in findings)
