"""Tests for core/gateway.py — resolve_resource, GATEWAY_RESOURCE_ALIASES, GatewayResult."""
from __future__ import annotations

import pytest

from horizon_research.core.gateway import (
    GATEWAY_RESOURCE_ALIASES,
    GatewayResult,
)


class TestGatewayResourceAliases:
    def test_singular_canonical(self):
        assert GATEWAY_RESOURCE_ALIASES["claim"] == "claim"
        assert GATEWAY_RESOURCE_ALIASES["parameter"] == "parameter"

    def test_plural_resolves(self):
        assert GATEWAY_RESOURCE_ALIASES["claims"] == "claim"
        assert GATEWAY_RESOURCE_ALIASES["predictions"] == "prediction"
        assert GATEWAY_RESOURCE_ALIASES["theories"] == "theory"

    def test_hyphenated_resolves(self):
        assert GATEWAY_RESOURCE_ALIASES["independence-group"] == "independence_group"
        assert GATEWAY_RESOURCE_ALIASES["dead-end"] == "dead_end"

    def test_underscored_resolves(self):
        assert GATEWAY_RESOURCE_ALIASES["independence_group"] == "independence_group"
        assert GATEWAY_RESOURCE_ALIASES["dead_end"] == "dead_end"

    def test_special_aliases(self):
        assert GATEWAY_RESOURCE_ALIASES["summary"] == "session_summary"
        assert GATEWAY_RESOURCE_ALIASES["session-summary"] == "session_summary"


class TestResolveResource:
    """Test Gateway.resolve_resource with a minimal Gateway instance."""

    @pytest.fixture
    def gateway(self):
        from unittest.mock import MagicMock
        from horizon_research.core.gateway import Gateway
        return Gateway(
            context=MagicMock(),
            repo=MagicMock(),
            validator=MagicMock(),
            renderer=MagicMock(),
            prose_sync=MagicMock(),
            tx_log=MagicMock(),
        )

    def test_canonical(self, gateway):
        assert gateway.resolve_resource("claim") == "claim"

    def test_plural(self, gateway):
        assert gateway.resolve_resource("predictions") == "prediction"

    def test_hyphenated(self, gateway):
        assert gateway.resolve_resource("dead-end") == "dead_end"

    def test_unknown_raises(self, gateway):
        with pytest.raises(KeyError, match="Unknown resource"):
            gateway.resolve_resource("bogus")


class TestGatewayResult:
    def test_defaults(self):
        r = GatewayResult(status="ok", changed=False, message="done")
        assert r.findings == []
        assert r.transaction_id is None
        assert r.data is None

    def test_full(self):
        from horizon_research.epistemic.types import Finding, Severity
        f = Finding(Severity.INFO, "s", "m")
        r = GatewayResult(
            status="BLOCKED",
            changed=True,
            message="blocked",
            findings=[f],
            transaction_id="tx-001",
            data={"key": "value"},
        )
        assert r.status == "BLOCKED"
        assert len(r.findings) == 1
        assert r.data["key"] == "value"
