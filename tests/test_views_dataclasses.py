"""Tests for view dataclasses — HealthReport, PredictionMetrics, WebMetrics, ProjectStatus."""
from __future__ import annotations

import pytest

from horizon_research.epistemic.types import Finding, Severity
from horizon_research.views.health import HealthReport


class TestHealthReport:
    def test_empty_report(self):
        r = HealthReport(overall="HEALTHY")
        assert r.critical_count == 0
        assert r.warning_count == 0
        assert r.findings == []

    def test_counts(self):
        findings = [
            Finding(Severity.CRITICAL, "a", "msg"),
            Finding(Severity.CRITICAL, "b", "msg"),
            Finding(Severity.WARNING, "c", "msg"),
            Finding(Severity.INFO, "d", "msg"),
        ]
        r = HealthReport(overall="CRITICAL", findings=findings)
        assert r.critical_count == 2
        assert r.warning_count == 1

    def test_overall_string(self):
        r = HealthReport(overall="WARNINGS")
        assert r.overall == "WARNINGS"
