"""MCP tool handlers — thin wrappers over the core and view services.

Every tool delegates immediately to the Gateway or a read-only service.
No business logic lives in this file.

Result envelopes follow the status-first convention:
  {"status": "ok" | "error" | "CLEAN" | "BLOCKED" | "dry_run", ...}

Core tool surface:
  register_resource   — register any entity type
  get_resource        — retrieve by ID
  list_resources      — list all of a type
  set_resource        — update fields on an existing entity
  transition_resource — change status
  query_web           — named read-only queries
  validate_web        — run all domain validators
  health_check        — composed health report
  project_status      — high-level status snapshot
  render_views        — regenerate markdown views
  check_stale         — identify analyses needing re-run
  check_refs          — verify all ID references are intact
  export_web          — bulk export (JSON or markdown)
"""
from __future__ import annotations

from ...config import ProjectContext
from ...controlplane.factory import build_gateway
from ...views.health import run_health_check
from ...views.status import get_status


def register_tools(server, context: ProjectContext) -> None:
    """Register all MCP tool handlers on the FastMCP server instance."""
    gateway = build_gateway(context)

    @server.tool()
    def register_resource(resource: str, payload: dict, dry_run: bool = False) -> dict:
        """Register a new entity in the epistemic web.

        resource: entity type — "claim", "assumption", "prediction", "analysis",
                  "theory", "discovery", "dead_end", "concept", "parameter",
                  "independence_group"
        payload:  entity fields as a dict
        dry_run:  if True, validate without writing to disk
        """
        return _envelope(gateway.register(resource, payload, dry_run=dry_run))

    @server.tool()
    def get_resource(resource: str, identifier: str) -> dict:
        """Retrieve a single entity by ID."""
        return _envelope(gateway.get(resource, identifier))

    @server.tool()
    def list_resources(resource: str) -> dict:
        """List all entities of a given type."""
        return _envelope(gateway.list(resource))

    @server.tool()
    def set_resource(
        resource: str, identifier: str, payload: dict, dry_run: bool = False
    ) -> dict:
        """Update fields on an existing entity."""
        return _envelope(gateway.set(resource, identifier, payload, dry_run=dry_run))

    @server.tool()
    def transition_resource(
        resource: str, identifier: str, new_status: str, dry_run: bool = False
    ) -> dict:
        """Transition an entity to a new status (e.g. PENDING → CONFIRMED)."""
        return _envelope(
            gateway.transition(resource, identifier, new_status, dry_run=dry_run)
        )

    @server.tool()
    def query_web(query_type: str, **params) -> dict:
        """Run a named read-only query across the epistemic web.

        query_type: "claim_lineage", "assumption_lineage", "prediction_chain", etc.
        """
        return _envelope(gateway.query(query_type, **params))

    @server.tool()
    def validate_web() -> dict:
        """Run all domain validators and return findings.

        Returns CLEAN or BLOCKED with a list of findings.
        """
        from ...controlplane.validate import validate_project
        findings = validate_project(context, gateway.repo)
        status = "CLEAN" if not any(
            f.severity.name == "CRITICAL" for f in findings
        ) else "BLOCKED"
        return {
            "status": status,
            "findings": [
                {"severity": f.severity.name, "source": f.source, "message": f.message}
                for f in findings
            ],
        }

    @server.tool()
    def health_check() -> dict:
        """Run all health checks and return a structured report.

        overall: "HEALTHY" | "WARNINGS" | "CRITICAL"
        """
        report = run_health_check(context, gateway.repo, gateway.validator)
        return {
            "status": report.overall,
            "critical": report.critical_count,
            "warnings": report.warning_count,
            "findings": [
                {"severity": f.severity.name, "source": f.source, "message": f.message}
                for f in report.findings
            ],
        }

    @server.tool()
    def project_status() -> dict:
        """Return a high-level project status snapshot."""
        from ...views.status import format_status_dict
        status = get_status(context, gateway.repo)
        return {"status": "ok", "data": format_status_dict(status)}

    @server.tool()
    def render_views(force: bool = False) -> dict:
        """Regenerate all markdown view surfaces.

        force: if True, re-render even if nothing has changed.
        """
        from ...views.render import render_all
        web = gateway.repo.load()
        written_by_surface = render_all(
            context,
            web,
            gateway.renderer,
            force=force,
        )
        return {
            "status": "ok",
            "changed": any(written_by_surface.values()),
            "message": "Rendered view surfaces",
            "data": {"written_by_surface": written_by_surface},
        }

    @server.tool()
    def check_stale() -> dict:
        """Identify analyses that need re-running after parameter changes.

        Returns analyses whose uses_parameters set includes a parameter
        that has changed since the analysis was last run.
        """
        from ...controlplane.check import check_stale
        findings = check_stale(context)
        return {
            "status": "ok",
            "findings": [
                {"severity": f.severity.name, "source": f.source, "message": f.message}
                for f in findings
            ],
        }

    @server.tool()
    def check_refs() -> dict:
        """Verify all ID cross-references in the epistemic web are intact."""
        from ...controlplane.check import check_refs
        findings = check_refs(context, gateway.repo)
        return {
            "status": "ok",
            "findings": [
                {"severity": f.severity.name, "source": f.source, "message": f.message}
                for f in findings
            ],
        }

    @server.tool()
    def export_web(fmt: str = "json", output_path: str | None = None) -> dict:
        """Bulk-export the epistemic web.

        fmt: "json" or "markdown"
        output_path: write to this path; if None, return in response data.
        """
        from pathlib import Path
        from ...controlplane.export import export_json, export_markdown
        out = Path(output_path) if output_path else context.paths.project_dir / "export"
        if fmt == "json":
            export_json(context, gateway.repo, out if output_path else out.with_suffix(".json"))
        else:
            export_markdown(context, gateway.repo, out)
        return {"status": "ok", "changed": True, "message": f"Exported as {fmt} to {out}"}


def _envelope(result) -> dict:
    """Convert a GatewayResult to a status-first MCP response dict."""
    out: dict = {
        "status": result.status,
        "changed": result.changed,
        "message": result.message,
    }
    if result.findings:
        out["findings"] = [
            {"severity": f.severity.name, "source": f.source, "message": f.message}
            for f in result.findings
        ]
    if result.transaction_id is not None:
        out["transaction_id"] = result.transaction_id
    if result.data is not None:
        out["data"] = result.data
    return out
