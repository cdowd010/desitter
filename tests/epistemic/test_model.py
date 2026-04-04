"""Tests for epistemic/model.py — all 10 entity dataclasses."""
from __future__ import annotations

from dataclasses import fields
from datetime import date

import pytest

from desitter.epistemic.model import (
    Analysis,
    Assumption,
    Claim,
    DeadEnd,
    Discovery,
    IndependenceGroup,
    PairwiseSeparation,
    Parameter,
    Prediction,
    Theory,
)
from desitter.epistemic.types import (
    AnalysisId,
    AssumptionId,
    AssumptionType,
    ClaimCategory,
    ClaimId,
    ClaimStatus,
    ClaimType,
    ConfidenceTier,
    DeadEndId,
    DeadEndStatus,
    DiscoveryId,
    DiscoveryStatus,
    EvidenceKind,
    IndependenceGroupId,
    MeasurementRegime,
    PairwiseSeparationId,
    ParameterId,
    PredictionId,
    PredictionStatus,
    TheoryId,
    TheoryStatus,
)


# ── Claim ─────────────────────────────────────────────────────────

class TestClaim:
    def test_minimal_construction(self):
        c = Claim(
            id=ClaimId("C-001"),
            statement="x > 0",
            type=ClaimType.FOUNDATIONAL,
            scope="global",
            falsifiability="measure x",
        )
        assert c.id == "C-001"
        assert c.status == ClaimStatus.ACTIVE
        assert c.category == ClaimCategory.QUALITATIVE
        assert c.assumptions == set()
        assert c.depends_on == set()
        assert c.analyses == set()
        assert c.parameter_constraints == {}
        assert c.source is None

    def test_full_construction(self):
        c = Claim(
            id=ClaimId("C-002"),
            statement="derived",
            type=ClaimType.DERIVED,
            scope="local",
            falsifiability="run test",
            status=ClaimStatus.REVISED,
            category=ClaimCategory.NUMERICAL,
            assumptions={AssumptionId("A-001")},
            depends_on={ClaimId("C-001")},
            analyses={AnalysisId("AN-001")},
            parameter_constraints={ParameterId("PAR-001"): "< 5"},
            source="arxiv:1234",
        )
        assert c.type is ClaimType.DERIVED
        assert ParameterId("PAR-001") in c.parameter_constraints

    def test_equality(self):
        kwargs = dict(
            id=ClaimId("C-001"), statement="s", type=ClaimType.FOUNDATIONAL,
            scope="g", falsifiability="f",
        )
        assert Claim(**kwargs) == Claim(**kwargs)


# ── Assumption ────────────────────────────────────────────────────

class TestAssumption:
    def test_defaults(self):
        a = Assumption(
            id=AssumptionId("A-001"),
            statement="flat spacetime",
            type=AssumptionType.EMPIRICAL,
            scope="global",
        )
        assert a.used_in_claims == set()
        assert a.depends_on == set()
        assert a.tested_by == set()
        assert a.falsifiable_consequence is None
        assert a.source is None
        assert a.notes is None

    def test_with_depends_on(self):
        a = Assumption(
            id=AssumptionId("A-002"),
            statement="linear detector",
            type=AssumptionType.METHODOLOGICAL,
            scope="detector",
            depends_on={AssumptionId("A-001")},
        )
        assert AssumptionId("A-001") in a.depends_on


# ── Prediction ────────────────────────────────────────────────────

class TestPrediction:
    def test_defaults(self):
        p = Prediction(
            id=PredictionId("P-001"),
            observable="obs",
            tier=ConfidenceTier.FULLY_SPECIFIED,
            status=PredictionStatus.PENDING,
            evidence_kind=EvidenceKind.NOVEL_PREDICTION,
            measurement_regime=MeasurementRegime.UNMEASURED,
            predicted=42,
        )
        assert p.free_params == 0
        assert p.claim_ids == set()
        assert p.tests_assumptions == set()
        assert p.conditional_on == set()
        assert p.correlation_tags == set()
        assert p.analysis is None
        assert p.independence_group is None
        assert p.observed is None

    def test_all_optional_fields(self):
        p = Prediction(
            id=PredictionId("P-002"),
            observable="mass",
            tier=ConfidenceTier.CONDITIONAL,
            status=PredictionStatus.CONFIRMED,
            evidence_kind=EvidenceKind.RETRODICTION,
            measurement_regime=MeasurementRegime.MEASURED,
            predicted=1.5,
            specification="m = E/c^2",
            derivation="from relativity",
            claim_ids={ClaimId("C-001")},
            tests_assumptions={AssumptionId("A-001")},
            analysis=AnalysisId("AN-001"),
            independence_group=IndependenceGroupId("IG-001"),
            correlation_tags={"mass", "energy"},
            observed=1.48,
            observed_bound=0.02,
            free_params=1,
            conditional_on={AssumptionId("A-002")},
            falsifier="new measurement",
            benchmark_source="PDG 2024",
            source="doi:10.1234",
            notes="note",
        )
        assert p.correlation_tags == {"mass", "energy"}


# ── IndependenceGroup ─────────────────────────────────────────────

class TestIndependenceGroup:
    def test_defaults(self):
        g = IndependenceGroup(
            id=IndependenceGroupId("IG-001"),
            label="group1",
        )
        assert g.claim_lineage == set()
        assert g.assumption_lineage == set()
        assert g.member_predictions == set()
        assert g.measurement_regime is None
        assert g.notes is None


# ── PairwiseSeparation ────────────────────────────────────────────

class TestPairwiseSeparation:
    def test_construction(self):
        s = PairwiseSeparation(
            id=PairwiseSeparationId("PS-001"),
            group_a=IndependenceGroupId("IG-001"),
            group_b=IndependenceGroupId("IG-002"),
            basis="orthogonal measurements",
        )
        assert s.group_a != s.group_b


# ── Analysis ──────────────────────────────────────────────────────

class TestAnalysis:
    def test_defaults(self):
        a = Analysis(id=AnalysisId("AN-001"))
        assert a.command is None
        assert a.path is None
        assert a.claims_covered == set()
        assert a.uses_parameters == set()
        assert a.notes is None


# ── Theory ────────────────────────────────────────────────────────

class TestTheory:
    def test_defaults(self):
        t = Theory(
            id=TheoryId("T-001"),
            title="General Relativity",
            status=TheoryStatus.ACTIVE,
        )
        assert t.related_claims == set()
        assert t.related_predictions == set()
        assert t.summary is None
        assert t.source is None

    def test_status_enum(self):
        t = Theory(
            id=TheoryId("T-002"),
            title="Superseded Theory",
            status=TheoryStatus.SUPERSEDED,
        )
        assert t.status is TheoryStatus.SUPERSEDED


# ── Discovery ─────────────────────────────────────────────────────

class TestDiscovery:
    def test_defaults(self):
        d = Discovery(
            id=DiscoveryId("D-001"),
            title="New particle",
            date=date(2026, 6, 15),
            summary="Found it",
            impact="High",
            status=DiscoveryStatus.NEW,
        )
        assert d.related_claims == set()
        assert d.related_predictions == set()
        assert d.references == []
        assert d.source is None


# ── DeadEnd ───────────────────────────────────────────────────────

class TestDeadEnd:
    def test_defaults(self):
        de = DeadEnd(
            id=DeadEndId("DE-001"),
            title="string theory variant",
            description="didn't pan out",
            status=DeadEndStatus.ACTIVE,
        )
        assert de.related_predictions == set()
        assert de.related_claims == set()
        assert de.references == []
        assert de.source is None



# ── Parameter ─────────────────────────────────────────────────────

class TestParameter:
    def test_defaults(self):
        p = Parameter(
            id=ParameterId("PAR-001"),
            name="alpha",
            value=0.0073,
        )
        assert p.unit is None
        assert p.uncertainty is None
        assert p.source is None
        assert p.used_in_analyses == set()
        assert p.notes is None

    def test_full(self):
        p = Parameter(
            id=ParameterId("PAR-002"),
            name="c",
            value=299792458,
            unit="m/s",
            uncertainty=0,
            source="NIST",
            notes="exact by definition",
        )
        assert p.unit == "m/s"


# ── Mutable defaults isolation ────────────────────────────────────

class TestMutableDefaults:
    """Ensure no mutable default sharing between instances."""

    def test_claim_sets_are_independent(self):
        a = Claim(id=ClaimId("C-001"), statement="a", type=ClaimType.FOUNDATIONAL,
                  scope="g", falsifiability="f")
        b = Claim(id=ClaimId("C-002"), statement="b", type=ClaimType.FOUNDATIONAL,
                  scope="g", falsifiability="f")
        a.assumptions.add(AssumptionId("A-001"))
        assert AssumptionId("A-001") not in b.assumptions

    def test_assumption_sets_are_independent(self):
        a = Assumption(id=AssumptionId("A-001"), statement="s", type=AssumptionType.EMPIRICAL, scope="g")
        b = Assumption(id=AssumptionId("A-002"), statement="s", type=AssumptionType.EMPIRICAL, scope="g")
        a.used_in_claims.add(ClaimId("C-001"))
        assert ClaimId("C-001") not in b.used_in_claims

    def test_parameter_sets_are_independent(self):
        a = Parameter(id=ParameterId("P-001"), name="x", value=1)
        b = Parameter(id=ParameterId("P-002"), name="y", value=2)
        a.used_in_analyses.add(AnalysisId("AN-001"))
        assert AnalysisId("AN-001") not in b.used_in_analyses
