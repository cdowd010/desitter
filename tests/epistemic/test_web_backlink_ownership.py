from __future__ import annotations

import pytest

from horizon_research.epistemic import DiscoveryStatus, TheoryStatus
from horizon_research.epistemic.model import (
    Analysis,
    Assumption,
    Claim,
    IndependenceGroup,
    PairwiseSeparation,
    Parameter,
    Prediction,
)
from horizon_research.epistemic.types import (
    AnalysisId,
    AssumptionId,
    AssumptionType,
    ClaimId,
    ClaimStatus,
    ClaimType,
    ConfidenceTier,
    EvidenceKind,
    IndependenceGroupId,
    MeasurementRegime,
    PairwiseSeparationId,
    ParameterId,
    PredictionId,
    PredictionStatus,
)
from horizon_research.epistemic.web import BrokenReferenceError, EpistemicWeb


def test_register_backlink_fields_are_owned_by_web() -> None:
    pid = ParameterId("PAR-1")
    aid = AnalysisId("AN-1")
    assump_id = AssumptionId("AS-1")
    claim_id = ClaimId("CL-1")
    group_id = IndependenceGroupId("IG-1")
    pred_id = PredictionId("PR-1")

    web = EpistemicWeb()

    # Parameter.used_in_analyses is a backlink owned by analysis operations.
    web = web.register_parameter(
        Parameter(
            id=pid,
            name="alpha",
            value=0.1,
            used_in_analyses={AnalysisId("AN-legacy")},
        )
    )
    assert web.parameters[pid].used_in_analyses == set()

    # Analysis.claims_covered is a backlink owned by claim operations.
    web = web.register_analysis(
        Analysis(
            id=aid,
            uses_parameters={pid},
            claims_covered={ClaimId("CL-legacy")},
        )
    )
    assert web.analyses[aid].claims_covered == set()
    assert web.parameters[pid].used_in_analyses == {aid}

    # Assumption.used_in_claims and Assumption.tested_by are backlinks.
    web = web.register_assumption(
        Assumption(
            id=assump_id,
            statement="Detector response is linear.",
            type=AssumptionType.EMPIRICAL,
            scope="global",
            used_in_claims={ClaimId("CL-legacy")},
            tested_by={PredictionId("PR-legacy")},
        )
    )
    assert web.assumptions[assump_id].used_in_claims == set()
    assert web.assumptions[assump_id].tested_by == set()

    web = web.register_claim(
        Claim(
            id=claim_id,
            statement="Signal amplitude scales with coupling.",
            type=ClaimType.DERIVED,
            scope="global",
            falsifiability="Contradicted by null scaling in controlled measurements.",
            status=ClaimStatus.ACTIVE,
            assumptions={assump_id},
            analyses={aid},
        )
    )
    assert web.assumptions[assump_id].used_in_claims == {claim_id}
    assert web.analyses[aid].claims_covered == {claim_id}

    # IndependenceGroup.member_predictions is a backlink owned by predictions.
    web = web.register_independence_group(
        IndependenceGroup(
            id=group_id,
            label="primary-chain",
            member_predictions={PredictionId("PR-legacy")},
        )
    )
    assert web.independence_groups[group_id].member_predictions == set()

    web = web.register_prediction(
        Prediction(
            id=pred_id,
            observable="amplitude",
            tier=ConfidenceTier.A,
            status=PredictionStatus.PENDING,
            evidence_kind=EvidenceKind.NOVEL_PREDICTION,
            measurement_regime=MeasurementRegime.UNMEASURED,
            predicted="positive scaling",
            claim_ids={claim_id},
            tests_assumptions={assump_id},
            independence_group=group_id,
        )
    )
    assert web.assumptions[assump_id].tested_by == {pred_id}
    assert web.independence_groups[group_id].member_predictions == {pred_id}


def test_pairwise_separation_requires_distinct_groups() -> None:
    g1 = IndependenceGroupId("IG-1")
    g2 = IndependenceGroupId("IG-2")
    sep_id = PairwiseSeparationId("PS-1")

    web = EpistemicWeb()
    web = web.register_independence_group(IndependenceGroup(id=g1, label="g1"))
    web = web.register_independence_group(IndependenceGroup(id=g2, label="g2"))

    with pytest.raises(BrokenReferenceError, match="distinct groups"):
        web.add_pairwise_separation(
            PairwiseSeparation(id=sep_id, group_a=g1, group_b=g1, basis="same")
        )

    web = web.add_pairwise_separation(
        PairwiseSeparation(id=sep_id, group_a=g1, group_b=g2, basis="different lineage")
    )

    with pytest.raises(BrokenReferenceError, match="distinct groups"):
        web.update_pairwise_separation(
            PairwiseSeparation(id=sep_id, group_a=g2, group_b=g2, basis="collapsed")
        )


def test_public_package_exports_new_status_enums() -> None:
    # Verifies the package-level public surface remains complete.
    assert TheoryStatus.ACTIVE.value == "active"
    assert DiscoveryStatus.NEW.value == "new"
