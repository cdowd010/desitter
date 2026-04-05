"""Tests for the public Python client API."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from desitter.client import DeSitterClient, DeSitterClientError, connect
from desitter.config import DesitterConfig, build_context
from desitter.controlplane.gateway import GatewayResult
from desitter.epistemic.codec import entity_to_dict
from desitter.epistemic.model import Claim, Prediction
from desitter.epistemic.types import (
    ClaimType,
    ConfidenceTier,
    EvidenceKind,
    Finding,
    MeasurementRegime,
    PredictionStatus,
    Severity,
)


class TestClientRoundTrip:
    def test_register_claim_and_prediction_round_trip(self, tmp_path):
        client = connect(tmp_path)

        claim_result = client.register_claim(
            id="C-001",
            statement="Catalyst X increases reaction yield.",
            type=ClaimType.FOUNDATIONAL,
            scope="global",
            falsifiability="A controlled experiment showing no yield increase would falsify it.",
        )
        assert claim_result.transaction_id is not None
        assert claim_result.data is not None
        assert isinstance(claim_result.data, Claim)

        fetched_claim = client.get_claim("C-001")
        assert fetched_claim.data is not None
        assert fetched_claim.data.statement == "Catalyst X increases reaction yield."

        prediction_result = client.register_prediction(
            id="P-001",
            observable="Mean treated-group yield",
            tier=ConfidenceTier.FULLY_SPECIFIED,
            status=PredictionStatus.PENDING,
            evidence_kind=EvidenceKind.NOVEL_PREDICTION,
            measurement_regime=MeasurementRegime.UNMEASURED,
            predicted=0.57,
            claim_ids=["C-001"],
        )
        assert prediction_result.transaction_id is not None
        assert prediction_result.data is not None
        assert isinstance(prediction_result.data, Prediction)

        fetched_prediction = client.get_prediction("P-001")
        assert fetched_prediction.data is not None
        assert fetched_prediction.data.claim_ids == {"C-001"}

        listed_predictions = client.list_predictions()
        assert listed_predictions.data is not None
        assert [prediction.id for prediction in listed_predictions.data] == ["P-001"]

        log_lines = client.context.paths.transaction_log_file.read_text(encoding="utf-8").splitlines()
        assert len(log_lines) == 2

    def test_connect_uses_project_dir_from_config(self, tmp_path):
        (tmp_path / "desitter.toml").write_text(
            '[desitter]\nproject_dir = "lab"\n',
            encoding="utf-8",
        )

        client = connect(tmp_path)

        assert client.context.paths.project_dir == tmp_path / "lab"

        client.register_parameter(id="PAR-001", name="alpha", value=0.05)
        assert (tmp_path / "lab" / "data" / "parameters.json").exists()


class TestConvenienceMethods:
    def test_entity_specific_methods_forward_expected_gateway_calls(self, tmp_path):
        context = build_context(tmp_path, DesitterConfig())
        gateway = MagicMock()

        claim = Claim(
            id="C-001",
            statement="Catalyst X increases reaction yield.",
            type=ClaimType.FOUNDATIONAL,
            scope="global",
            falsifiability="A null result would falsify it.",
        )
        prediction = Prediction(
            id="P-001",
            observable="Mean treated-group yield",
            tier=ConfidenceTier.FULLY_SPECIFIED,
            status=PredictionStatus.PENDING,
            evidence_kind=EvidenceKind.NOVEL_PREDICTION,
            measurement_regime=MeasurementRegime.UNMEASURED,
            predicted=0.57,
            claim_ids={"C-001"},
        )
        gateway.register.side_effect = [
            GatewayResult(
                status="ok",
                changed=True,
                message="Registered claim",
                data={"resource": entity_to_dict(claim)},
            ),
            GatewayResult(
                status="ok",
                changed=True,
                message="Registered prediction",
                data={"resource": entity_to_dict(prediction)},
            ),
        ]

        client = DeSitterClient(context, gateway=gateway)

        client.register_claim(
            id="C-001",
            statement="Catalyst X increases reaction yield.",
            type=ClaimType.FOUNDATIONAL,
            scope="global",
            falsifiability="A null result would falsify it.",
        )
        gateway.register.assert_any_call(
            "claim",
            {
                "id": "C-001",
                "statement": "Catalyst X increases reaction yield.",
                "type": ClaimType.FOUNDATIONAL,
                "scope": "global",
                "falsifiability": "A null result would falsify it.",
            },
            dry_run=False,
        )

        client.register_prediction(
            id="P-001",
            observable="Mean treated-group yield",
            tier=ConfidenceTier.FULLY_SPECIFIED,
            status=PredictionStatus.PENDING,
            evidence_kind=EvidenceKind.NOVEL_PREDICTION,
            measurement_regime=MeasurementRegime.UNMEASURED,
            predicted=0.57,
            claim_ids=["C-001"],
        )
        gateway.register.assert_any_call(
            "prediction",
            {
                "id": "P-001",
                "observable": "Mean treated-group yield",
                "tier": ConfidenceTier.FULLY_SPECIFIED,
                "status": PredictionStatus.PENDING,
                "evidence_kind": EvidenceKind.NOVEL_PREDICTION,
                "measurement_regime": MeasurementRegime.UNMEASURED,
                "predicted": 0.57,
                "claim_ids": ["C-001"],
            },
            dry_run=False,
        )


class TestClientErrors:
    def test_schema_errors_surface_cleanly(self, tmp_path):
        client = connect(tmp_path)

        with pytest.raises(DeSitterClientError) as exc_info:
            client.register(
                "claim",
                statement="Missing the required id field.",
                type=ClaimType.FOUNDATIONAL,
                scope="global",
                falsifiability="A null result would falsify it.",
            )

        error = exc_info.value
        assert error.status == "error"
        assert error.findings
        assert error.findings[0].severity == Severity.CRITICAL
        assert error.findings[0].source == "payload/claim"
        assert "Payload validation failed" in error.message

    def test_gateway_errors_are_wrapped(self, tmp_path):
        context = build_context(tmp_path, DesitterConfig())
        gateway = MagicMock()
        gateway.register.return_value = GatewayResult(
            status="error",
            changed=False,
            message="broken payload",
            findings=[Finding(Severity.CRITICAL, "payload/claim", "broken payload")],
        )

        client = DeSitterClient(context, gateway=gateway)

        with pytest.raises(DeSitterClientError, match="broken payload"):
            client.register(
                "claim",
                id="C-001",
                statement="Claim",
                type=ClaimType.FOUNDATIONAL,
                scope="global",
                falsifiability="Testable",
            )