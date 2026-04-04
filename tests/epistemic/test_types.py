"""Tests for epistemic/types.py — enums, Finding, and typed IDs."""
from __future__ import annotations

import pytest

from horizon_research.epistemic.types import (
    AssumptionId,
    AssumptionType,
    ClaimCategory,
    ClaimId,
    ClaimStatus,
    ClaimType,
    ConfidenceTier,
    DeadEndStatus,
    DiscoveryStatus,
    EvidenceKind,
    Finding,
    MeasurementRegime,
    PredictionStatus,
    Severity,
    TheoryStatus,
)


# ── Severity ──────────────────────────────────────────────────────

class TestSeverity:
    def test_members(self):
        assert set(Severity) == {Severity.INFO, Severity.WARNING, Severity.CRITICAL}

    def test_auto_values_are_distinct(self):
        vals = [s.value for s in Severity]
        assert len(vals) == len(set(vals))


# ── Finding ───────────────────────────────────────────────────────

class TestFinding:
    def test_construction(self):
        f = Finding(Severity.WARNING, "claims/C-001", "problem description")
        assert f.severity is Severity.WARNING
        assert f.source == "claims/C-001"
        assert f.message == "problem description"

    def test_equality(self):
        a = Finding(Severity.INFO, "s", "m")
        b = Finding(Severity.INFO, "s", "m")
        assert a == b

    def test_inequality(self):
        a = Finding(Severity.INFO, "s", "m")
        b = Finding(Severity.CRITICAL, "s", "m")
        assert a != b


# ── ConfidenceTier ────────────────────────────────────────────────

class TestConfidenceTier:
    def test_values(self):
        assert ConfidenceTier.A.value == "A"
        assert ConfidenceTier.B.value == "B"
        assert ConfidenceTier.C.value == "C"

    def test_lookup_by_value(self):
        assert ConfidenceTier("A") is ConfidenceTier.A

    def test_member_count(self):
        assert len(ConfidenceTier) == 3


# ── EvidenceKind ──────────────────────────────────────────────────

class TestEvidenceKind:
    def test_members(self):
        assert {e.value for e in EvidenceKind} == {
            "novel_prediction", "retrodiction", "fit_consistency",
        }


# ── MeasurementRegime ────────────────────────────────────────────

class TestMeasurementRegime:
    def test_members(self):
        assert {m.value for m in MeasurementRegime} == {
            "measured", "bound_only", "unmeasured",
        }


# ── PredictionStatus ─────────────────────────────────────────────

class TestPredictionStatus:
    def test_members(self):
        assert {s.value for s in PredictionStatus} == {
            "CONFIRMED", "STRESSED", "REFUTED", "PENDING", "NOT_YET_TESTABLE",
        }


# ── DeadEndStatus ────────────────────────────────────────────────

class TestDeadEndStatus:
    def test_members(self):
        assert {s.value for s in DeadEndStatus} == {
            "active", "resolved", "archived",
        }


# ── TheoryStatus ─────────────────────────────────────────────────

class TestTheoryStatus:
    def test_members(self):
        assert {s.value for s in TheoryStatus} == {
            "active", "refined", "abandoned", "superseded",
        }


# ── DiscoveryStatus ──────────────────────────────────────────────

class TestDiscoveryStatus:
    def test_members(self):
        assert {s.value for s in DiscoveryStatus} == {
            "new", "integrated", "archived",
        }


# ── ClaimStatus ──────────────────────────────────────────────────

class TestClaimStatus:
    def test_members(self):
        assert {s.value for s in ClaimStatus} == {
            "active", "revised", "retracted",
        }


# ── ClaimType ────────────────────────────────────────────────────

class TestClaimType:
    def test_members(self):
        assert {ct.value for ct in ClaimType} == {
            "foundational", "derived",
        }


# ── ClaimCategory ────────────────────────────────────────────────

class TestClaimCategory:
    def test_members(self):
        assert {cc.value for cc in ClaimCategory} == {
            "numerical", "qualitative",
        }


# ── AssumptionType ───────────────────────────────────────────────

class TestAssumptionType:
    def test_members(self):
        assert {at.value for at in AssumptionType} == {"E", "M"}


# ── NewType IDs ──────────────────────────────────────────────────

class TestNewTypeIds:
    """NewType creates identity functions — runtime type is still str."""

    def test_claim_id_is_str(self):
        cid = ClaimId("C-001")
        assert isinstance(cid, str)
        assert cid == "C-001"

    def test_assumption_id_is_str(self):
        aid = AssumptionId("A-001")
        assert isinstance(aid, str)
