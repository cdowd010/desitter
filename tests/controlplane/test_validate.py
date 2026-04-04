"""Tests for core/validate.py — DomainValidator."""
from __future__ import annotations

import pytest

from horizon_research.core.validate import DomainValidator
from horizon_research.epistemic.types import ConfidenceTier, Severity
from horizon_research.epistemic.web import EpistemicWeb

from tests.epistemic.conftest import make_prediction


class TestDomainValidator:
    def test_clean_web(self):
        validator = DomainValidator()
        findings = validator.validate(EpistemicWeb())
        assert findings == []

    def test_delegates_to_invariants(self):
        """Ensures DomainValidator.validate() returns findings from validate_all."""
        web = EpistemicWeb()
        web = web.register_prediction(
            make_prediction(1, tier=ConfidenceTier.A, free_params=5)
        )
        validator = DomainValidator()
        findings = validator.validate(web)
        assert len(findings) > 0
        assert any(f.severity == Severity.CRITICAL for f in findings)
