"""The single mutation/query boundary for the control plane.

Both the MCP server and the CLI route all operations through the Gateway.
There is no MCP-specific or CLI-specific business logic — the Gateway is
the one implementation.

Responsibilities:
  - Resource-oriented register/get/list/set/transition/query operations
  - Payload parsing and normalization
  - Resource alias resolution (plural/hyphenated → canonical keys)
  - Dry-run semantics
  - Transaction orchestration (validate-after-write, rollback on failure)
  - Provenance logging via TransactionLog

Not responsible for:
  - Storing canonical domain rules in untyped dicts
  - Mutating module globals
  - Owning validation rules themselves
  - Formatting human CLI output
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..epistemic.ports import (
    ProseSync,
    TransactionLog,
    WebRepository,
    WebRenderer,
    WebValidator,
)
from ..epistemic.types import Finding
from ..config import ProjectContext


# Maps plural/hyphenated CLI forms to canonical resource keys.
# Adding a new resource type means adding one entry here.
GATEWAY_RESOURCE_ALIASES: dict[str, str] = {
    "claim": "claim",
    "claims": "claim",
    "assumption": "assumption",
    "assumptions": "assumption",
    "prediction": "prediction",
    "predictions": "prediction",
    "analysis": "analysis",
    "analyses": "analysis",
    "independence-group": "independence_group",
    "independence_group": "independence_group",
    "independence-groups": "independence_group",
    "independence_groups": "independence_group",
    "theory": "theory",
    "theories": "theory",
    "discovery": "discovery",
    "discoveries": "discovery",
    "dead-end": "dead_end",
    "dead_end": "dead_end",
    "dead-ends": "dead_end",
    "dead_ends": "dead_end",
    "parameter": "parameter",
    "parameters": "parameter",
    "summary": "session_summary",
    "session-summary": "session_summary",
}


@dataclass
class GatewayResult:
    """Stable result envelope returned by every gateway operation.

    Consumed by both MCP tool handlers and CLI formatters.

    status:         "ok" | "error" | "CLEAN" | "BLOCKED" | "dry_run"
    changed:        True if the persistent state was modified.
    message:        Human-readable summary.
    findings:       Validation findings (may be empty).
    transaction_id: Set for mutations; None for read-only operations.
    data:           Resource payload for get/list/query results.
    """
    status: str
    changed: bool
    message: str
    findings: list[Finding] = field(default_factory=list)
    transaction_id: str | None = None
    data: dict | None = None


class Gateway:
    """Single mutation/query boundary for the control plane."""

    def __init__(
        self,
        context: ProjectContext,
        repo: WebRepository,
        validator: WebValidator,
        renderer: WebRenderer,
        prose_sync: ProseSync,
        tx_log: TransactionLog,
    ) -> None:
        """Initialize a fully wired gateway service boundary.

        Args:
            context: Project paths and runtime configuration.
            repo: Persistence adapter for loading/saving the web.
            validator: Domain validation service.
            renderer: View renderer for markdown outputs.
            prose_sync: Adapter that synchronizes prose artifacts.
            tx_log: Provenance logger for operations.
        """
        self._context = context
        self._repo = repo
        self._validator = validator
        self._renderer = renderer
        self._prose_sync = prose_sync
        self._tx_log = tx_log

    @property
    def repo(self) -> WebRepository:
        """Read-only access to repository dependency for read services."""
        return self._repo

    @property
    def validator(self) -> WebValidator:
        """Read-only access to validator dependency for health/report services."""
        return self._validator

    @property
    def renderer(self) -> WebRenderer:
        """Read-only access to renderer dependency for view generation services."""
        return self._renderer

    def resolve_resource(self, alias: str) -> str:
        """Resolve a resource alias to its canonical key.

        Raises KeyError if the alias is not recognised.
        """
        key = GATEWAY_RESOURCE_ALIASES.get(alias)
        if key is None:
            raise KeyError(f"Unknown resource type: {alias!r}")
        return key

    def register(
        self,
        resource: str,
        payload: dict,
        *,
        dry_run: bool = False,
    ) -> GatewayResult:
        """Register a new resource entity.

        Validates after write; rolls back on invariant violation.
        Logs the transaction and returns a GatewayResult.
        """
        raise NotImplementedError

    def get(self, resource: str, identifier: str) -> GatewayResult:
        """Retrieve a single resource by ID."""
        raise NotImplementedError

    def list(self, resource: str, **filters: object) -> GatewayResult:
        """List resources, optionally filtered."""
        raise NotImplementedError

    def set(
        self,
        resource: str,
        identifier: str,
        payload: dict,
        *,
        dry_run: bool = False,
    ) -> GatewayResult:
        """Update fields on an existing resource."""
        raise NotImplementedError

    def transition(
        self,
        resource: str,
        identifier: str,
        new_status: str,
        *,
        dry_run: bool = False,
    ) -> GatewayResult:
        """Transition a resource to a new status."""
        raise NotImplementedError

    def query(self, query_type: str, **params: object) -> GatewayResult:
        """Run a named read-only query across the web."""
        raise NotImplementedError
