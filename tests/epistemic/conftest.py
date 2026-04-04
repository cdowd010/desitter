"""Shared fixtures for epistemic tests.

Builds progressively richer webs so individual test modules can focus
on the behaviour they care about without duplicating setup boilerplate.
"""
from __future__ import annotations

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
from desitter.epistemic.web import EpistemicWeb


# ── ID factories ──────────────────────────────────────────────────

def make_claim_id(n: int = 1) -> ClaimId:
    return ClaimId(f"C-{n:03d}")

def make_assumption_id(n: int = 1) -> AssumptionId:
    return AssumptionId(f"A-{n:03d}")

def make_prediction_id(n: int = 1) -> PredictionId:
    return PredictionId(f"P-{n:03d}")

def make_analysis_id(n: int = 1) -> AnalysisId:
    return AnalysisId(f"AN-{n:03d}")

def make_parameter_id(n: int = 1) -> ParameterId:
    return ParameterId(f"PAR-{n:03d}")

def make_theory_id(n: int = 1) -> TheoryId:
    return TheoryId(f"T-{n:03d}")

def make_discovery_id(n: int = 1) -> DiscoveryId:
    return DiscoveryId(f"D-{n:03d}")

def make_dead_end_id(n: int = 1) -> DeadEndId:
    return DeadEndId(f"DE-{n:03d}")

def make_group_id(n: int = 1) -> IndependenceGroupId:
    return IndependenceGroupId(f"IG-{n:03d}")

def make_sep_id(n: int = 1) -> PairwiseSeparationId:
    return PairwiseSeparationId(f"PS-{n:03d}")


# ── Entity factories ─────────────────────────────────────────────

def make_parameter(n: int = 1, **overrides) -> Parameter:
    defaults = dict(id=make_parameter_id(n), name=f"param_{n}", value=float(n))
    defaults.update(overrides)
    return Parameter(**defaults)

def make_assumption(n: int = 1, **overrides) -> Assumption:
    defaults = dict(
        id=make_assumption_id(n),
        statement=f"Assumption {n}",
        type=AssumptionType.EMPIRICAL,
        scope="global",
    )
    defaults.update(overrides)
    return Assumption(**defaults)

def make_claim(n: int = 1, **overrides) -> Claim:
    defaults = dict(
        id=make_claim_id(n),
        statement=f"Claim {n}",
        type=ClaimType.FOUNDATIONAL,
        scope="global",
        falsifiability=f"Falsifiable by test {n}",
    )
    defaults.update(overrides)
    return Claim(**defaults)

def make_analysis(n: int = 1, **overrides) -> Analysis:
    defaults = dict(id=make_analysis_id(n))
    defaults.update(overrides)
    return Analysis(**defaults)

def make_prediction(n: int = 1, **overrides) -> Prediction:
    defaults = dict(
        id=make_prediction_id(n),
        observable=f"observable_{n}",
        tier=ConfidenceTier.FULLY_SPECIFIED,
        status=PredictionStatus.PENDING,
        evidence_kind=EvidenceKind.NOVEL_PREDICTION,
        measurement_regime=MeasurementRegime.UNMEASURED,
        predicted=f"value_{n}",
    )
    defaults.update(overrides)
    return Prediction(**defaults)

def make_theory(n: int = 1, **overrides) -> Theory:
    defaults = dict(
        id=make_theory_id(n),
        title=f"Theory {n}",
        status=TheoryStatus.ACTIVE,
    )
    defaults.update(overrides)
    return Theory(**defaults)

def make_discovery(n: int = 1, **overrides) -> Discovery:
    defaults = dict(
        id=make_discovery_id(n),
        title=f"Discovery {n}",
        date=date(2026, 1, (n % 28) + 1),
        summary=f"Summary {n}",
        impact=f"Impact {n}",
        status=DiscoveryStatus.NEW,
    )
    defaults.update(overrides)
    return Discovery(**defaults)

def make_dead_end(n: int = 1, **overrides) -> DeadEnd:
    defaults = dict(
        id=make_dead_end_id(n),
        title=f"Dead end {n}",
        description=f"Description {n}",
        status=DeadEndStatus.ACTIVE,
    )
    defaults.update(overrides)
    return DeadEnd(**defaults)

def make_group(n: int = 1, **overrides) -> IndependenceGroup:
    defaults = dict(id=make_group_id(n), label=f"group_{n}")
    defaults.update(overrides)
    return IndependenceGroup(**defaults)

def make_separation(n: int = 1, **overrides) -> PairwiseSeparation:
    defaults = dict(
        id=make_sep_id(n),
        group_a=make_group_id(1),
        group_b=make_group_id(2),
        basis=f"Separation basis {n}",
    )
    defaults.update(overrides)
    return PairwiseSeparation(**defaults)


# ── Progressively richer web fixtures ─────────────────────────────

@pytest.fixture
def empty_web() -> EpistemicWeb:
    return EpistemicWeb()


@pytest.fixture
def web_with_params(empty_web: EpistemicWeb) -> EpistemicWeb:
    """Web with two parameters."""
    web = empty_web
    web = web.register_parameter(make_parameter(1))
    web = web.register_parameter(make_parameter(2))
    return web


@pytest.fixture
def web_with_analysis(web_with_params: EpistemicWeb) -> EpistemicWeb:
    """Web with params and an analysis using param 1."""
    return web_with_params.register_analysis(
        make_analysis(1, uses_parameters={make_parameter_id(1)})
    )


@pytest.fixture
def web_with_assumptions(empty_web: EpistemicWeb) -> EpistemicWeb:
    """Web with two independent assumptions."""
    web = empty_web
    web = web.register_assumption(make_assumption(1))
    web = web.register_assumption(make_assumption(2))
    return web


@pytest.fixture
def web_with_claim_chain(web_with_assumptions: EpistemicWeb) -> EpistemicWeb:
    """Web with assumptions, a foundational claim, and a derived claim depending on it."""
    web = web_with_assumptions
    web = web.register_claim(
        make_claim(1, assumptions={make_assumption_id(1)})
    )
    web = web.register_claim(
        make_claim(
            2,
            type=ClaimType.DERIVED,
            assumptions={make_assumption_id(2)},
            depends_on={make_claim_id(1)},
        )
    )
    return web


@pytest.fixture
def rich_web() -> EpistemicWeb:
    """A web with at least one of every entity type, fully linked."""
    web = EpistemicWeb()
    # Parameters
    web = web.register_parameter(make_parameter(1))
    # Analysis using that parameter
    web = web.register_analysis(
        make_analysis(1, uses_parameters={make_parameter_id(1)})
    )
    # Assumptions (A-001 depends on nothing, A-002 depends on A-001)
    web = web.register_assumption(make_assumption(1))
    web = web.register_assumption(
        make_assumption(2, depends_on={make_assumption_id(1)})
    )
    # Claims
    web = web.register_claim(
        make_claim(
            1,
            assumptions={make_assumption_id(1)},
            analyses={make_analysis_id(1)},
            category=ClaimCategory.NUMERICAL,
        )
    )
    web = web.register_claim(
        make_claim(
            2,
            type=ClaimType.DERIVED,
            assumptions={make_assumption_id(2)},
            depends_on={make_claim_id(1)},
        )
    )
    # Independence group
    web = web.register_independence_group(
        make_group(1, claim_lineage={make_claim_id(1)})
    )
    # Prediction
    web = web.register_prediction(
        make_prediction(
            1,
            claim_ids={make_claim_id(1), make_claim_id(2)},
            tests_assumptions={make_assumption_id(1)},
            analysis=make_analysis_id(1),
            independence_group=make_group_id(1),
        )
    )
    # Theory
    web = web.register_theory(
        make_theory(1, related_claims={make_claim_id(1)})
    )
    # Discovery
    web = web.register_discovery(make_discovery(1))
    # Dead end
    web = web.register_dead_end(make_dead_end(1))
    return web
