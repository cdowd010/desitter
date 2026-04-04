"""Tests for epistemic/ports.py — protocol structural subtyping."""
from __future__ import annotations

from horizon_research.epistemic.ports import (
    ProseSync,
    TransactionLog,
    WebRenderer,
    WebRepository,
    WebValidator,
)
from horizon_research.epistemic.types import Finding, Severity
from horizon_research.epistemic.web import EpistemicWeb


class _FakeRepo:
    def load(self) -> EpistemicWeb:
        return EpistemicWeb()

    def save(self, web: EpistemicWeb) -> None:
        pass


class _FakeRenderer:
    def render(self, web: EpistemicWeb) -> dict[str, str]:
        return {}


class _FakeValidator:
    def validate(self, web: EpistemicWeb) -> list[Finding]:
        return [Finding(Severity.INFO, "test", "ok")]


class _FakeProseSync:
    def sync(self, web: EpistemicWeb) -> dict[str, object]:
        return {}


class _FakeTxLog:
    def append(self, operation: str, identifier: str) -> str:
        return "tx-001"


class TestProtocolCompliance:
    """Verify that simple implementations satisfy the Protocol structurally."""

    def test_web_repository(self):
        repo: WebRepository = _FakeRepo()
        web = repo.load()
        assert isinstance(web, EpistemicWeb)
        repo.save(web)

    def test_web_renderer(self):
        renderer: WebRenderer = _FakeRenderer()
        result = renderer.render(EpistemicWeb())
        assert isinstance(result, dict)

    def test_web_validator(self):
        validator: WebValidator = _FakeValidator()
        findings = validator.validate(EpistemicWeb())
        assert len(findings) == 1

    def test_prose_sync(self):
        sync: ProseSync = _FakeProseSync()
        result = sync.sync(EpistemicWeb())
        assert isinstance(result, dict)

    def test_transaction_log(self):
        log: TransactionLog = _FakeTxLog()
        tx_id = log.append("register", "C-001")
        assert tx_id == "tx-001"
