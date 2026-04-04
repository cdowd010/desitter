"""CLI entry point — thin adapter over core and view services.

All commands construct a ProjectContext, wire a Gateway, and delegate
to the appropriate service. No business logic here.

Command surface (mirrors MCP tools):
  horizon register <resource>        — register entity (payload from stdin or --data)
  horizon get <resource> <id>        — retrieve by ID
  horizon list <resource>            — list all of a type
  horizon set <resource> <id>        — update fields (payload from stdin or --data)
  horizon transition <resource> <id> <status>
  horizon validate                   — run all domain validators
  horizon health                     — composed health report
  horizon status                     — high-level project snapshot
  horizon render [--force]           — regenerate markdown views
  horizon export [--format json|md]  — bulk export
  horizon init                       — initialise a new project workspace
"""
from __future__ import annotations

from pathlib import Path

import click

from ...config import build_context, load_config
from .formatters import print_gateway_result, print_health_report, print_status


@click.group()
@click.option(
    "--workspace",
    "-w",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=None,
    help="Project workspace directory (defaults to cwd).",
)
@click.option("--json", "output_json", is_flag=True, help="Output as JSON.")
@click.pass_context
def cli(ctx: click.Context, workspace: Path | None, output_json: bool) -> None:
    """Horizon Research — epistemic web data system."""
    ws = workspace or Path.cwd()
    config = load_config(ws)
    context = build_context(ws, config)
    ctx.ensure_object(dict)
    ctx.obj["context"] = context
    ctx.obj["output_json"] = output_json


@cli.command()
@click.argument("resource")
@click.option("--data", "-d", default=None, help="JSON payload string.")
@click.option("--dry-run", is_flag=True)
@click.pass_context
def register(ctx: click.Context, resource: str, data: str | None, dry_run: bool) -> None:
    """Register a new entity. Reads JSON payload from --data or stdin."""
    raise NotImplementedError


@cli.command()
@click.argument("resource")
@click.argument("identifier")
@click.pass_context
def get(ctx: click.Context, resource: str, identifier: str) -> None:
    """Retrieve a single entity by ID."""
    raise NotImplementedError


@cli.command("list")
@click.argument("resource")
@click.pass_context
def list_resources(ctx: click.Context, resource: str) -> None:
    """List all entities of a given type."""
    raise NotImplementedError


@cli.command()
@click.argument("resource")
@click.argument("identifier")
@click.option("--data", "-d", default=None, help="JSON payload string.")
@click.option("--dry-run", is_flag=True)
@click.pass_context
def set(ctx: click.Context, resource: str, identifier: str, data: str | None, dry_run: bool) -> None:
    """Update fields on an existing entity."""
    raise NotImplementedError


@cli.command()
@click.argument("resource")
@click.argument("identifier")
@click.argument("new_status")
@click.option("--dry-run", is_flag=True)
@click.pass_context
def transition(
    ctx: click.Context, resource: str, identifier: str, new_status: str, dry_run: bool
) -> None:
    """Transition an entity to a new status."""
    raise NotImplementedError


@cli.command()
@click.pass_context
def validate(ctx: click.Context) -> None:
    """Run all domain validators and print findings."""
    raise NotImplementedError


@cli.command()
@click.pass_context
def health(ctx: click.Context) -> None:
    """Run all health checks and print a structured report."""
    raise NotImplementedError


@cli.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Print a high-level project status snapshot."""
    raise NotImplementedError


@cli.command()
@click.option("--force", is_flag=True, help="Re-render even if nothing has changed.")
@click.pass_context
def render(ctx: click.Context, force: bool) -> None:
    """Regenerate all markdown view surfaces."""
    raise NotImplementedError


@cli.command()
@click.option(
    "--format", "fmt", type=click.Choice(["json", "markdown"]), default="json"
)
@click.option("--output", "-o", type=click.Path(path_type=Path), default=None)
@click.pass_context
def export(ctx: click.Context, fmt: str, output: Path | None) -> None:
    """Bulk-export the epistemic web as JSON or markdown."""
    raise NotImplementedError


@cli.command()
@click.option("--workspace", "ws_path", type=click.Path(path_type=Path), default=None)
def init(ws_path: Path | None) -> None:
    """Initialise a new Horizon project workspace.

    Creates project_config.json and the standard directory layout.
    Idempotent — safe to run on an existing workspace.
    """
    raise NotImplementedError


def main() -> None:
    cli()
