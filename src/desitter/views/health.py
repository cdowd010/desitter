"""Health checks for the project.

Composes validation, render-staleness, and structure checks into a single
health report. Intended as the primary "is everything OK?" command for
both MCP tools and the CLI.

Returns a structured report rather than raw findings, so callers can
make automated pass/fail decisions.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..epistemic.ports import WebRepository, WebValidator
from ..epistemic.types import Finding, Severity
from ..config import ProjectContext


@dataclass
class HealthReport:
    """Structured health report for a project.

    overall:  "HEALTHY" | "WARNINGS" | "CRITICAL"
    findings: All findings from all checks, sorted by severity.
    """
    overall: str
    findings: list[Finding] = field(default_factory=list)

    @property
    def critical_count(self) -> int:
        """Count CRITICAL findings in the aggregated report."""
        return sum(1 for f in self.findings if f.severity == Severity.CRITICAL)

    @property
    def warning_count(self) -> int:
        """Count WARNING findings in the aggregated report."""
        return sum(1 for f in self.findings if f.severity == Severity.WARNING)


def run_health_check(
    context: ProjectContext,
    repo: WebRepository,
    validator: WebValidator,
) -> HealthReport:
    """Run all health checks and return a structured report.

    Checks performed:
      1. Domain invariant validation (epistemic/invariants.py)
      2. Render staleness (views/render.py)
      3. File structure integrity (controlplane/validate.py)
    """
    raise NotImplementedError
