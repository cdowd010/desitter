"""The single mutation/query boundary for the control plane.

Both the MCP server and the CLI route all operations through the Gateway.
There is no MCP-specific or CLI-specific business logic — the Gateway is
the one implementation.

Responsibilities:
  - Resource-oriented register/get/list/set/transition/query operations
  - Payload parsing and normalization
  - Resource alias resolution (plural/hyphenated → canonical keys)
  - Dry-run semantics
    - Transaction orchestration (validate after mutation, persist only on success)
  - Provenance logging via TransactionLog

Not responsible for:
  - Storing canonical domain rules in untyped dicts
  - Mutating module globals
  - Owning validation rules themselves
  - Formatting human CLI output
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..epistemic.codec import (
    build_entity,
    entity_id_type,
    entity_to_dict,
    normalize_payload,
    serialize_value,
    status_enum_type,
)
from ..epistemic.ports import (
    PayloadValidator,
    ProseSync,
    TransactionLog,
    WebRepository,
    WebRenderer,
    WebValidator,
)
from ..epistemic.types import Finding, Severity
from ..epistemic.web import EpistemicError
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
    "pairwise-separation": "pairwise_separation",
    "pairwise_separation": "pairwise_separation",
    "pairwise-separations": "pairwise_separation",
    "pairwise_separations": "pairwise_separation",
    "summary": "session_summary",
    "session-summary": "session_summary",
}


@dataclass(frozen=True)
class _ResourceSpec:
    collection_attr: str
    register_method: str
    update_method: str
    transition_method: str | None = None


@dataclass(frozen=True)
class _QuerySpec:
    method_name: str
    parameter_resources: dict[str, str]


_RESOURCE_SPECS: dict[str, _ResourceSpec] = {
    "claim": _ResourceSpec("claims", "register_claim", "update_claim", "transition_claim"),
    "assumption": _ResourceSpec("assumptions", "register_assumption", "update_assumption"),
    "prediction": _ResourceSpec("predictions", "register_prediction", "update_prediction", "transition_prediction"),
    "analysis": _ResourceSpec("analyses", "register_analysis", "update_analysis"),
    "theory": _ResourceSpec("theories", "register_theory", "update_theory", "transition_theory"),
    "discovery": _ResourceSpec("discoveries", "register_discovery", "update_discovery", "transition_discovery"),
    "dead_end": _ResourceSpec("dead_ends", "register_dead_end", "update_dead_end", "transition_dead_end"),
    "parameter": _ResourceSpec("parameters", "register_parameter", "update_parameter"),
    "independence_group": _ResourceSpec("independence_groups", "register_independence_group", "update_independence_group"),
    "pairwise_separation": _ResourceSpec("pairwise_separations", "add_pairwise_separation", "update_pairwise_separation"),
}


_QUERY_SPECS: dict[str, _QuerySpec] = {
    "claim_lineage": _QuerySpec("claim_lineage", {"cid": "claim"}),
    "assumption_lineage": _QuerySpec("assumption_lineage", {"cid": "claim"}),
    "prediction_implicit_assumptions": _QuerySpec(
        "prediction_implicit_assumptions",
        {"pid": "prediction"},
    ),
    "refutation_impact": _QuerySpec("refutation_impact", {"pid": "prediction"}),
    "assumption_support_status": _QuerySpec(
        "assumption_support_status",
        {"aid": "assumption"},
    ),
    "predictions_depending_on_claim": _QuerySpec(
        "predictions_depending_on_claim",
        {"cid": "claim"},
    ),
    "parameter_impact": _QuerySpec("parameter_impact", {"pid": "parameter"}),
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
        payload_validator: PayloadValidator | None = None,
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
        self._payload_validator = payload_validator

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

        Validates after mutation and before persistence.
        Persists only on success, logs the transaction, and returns a
        GatewayResult.
        """
        try:
            canonical = self.resolve_resource(resource)
            spec = self._resource_spec(canonical)
        except KeyError as exc:
            return self._error_result(str(exc))

        normalized_payload = normalize_payload(payload)
        payload_findings = self._validate_payload(canonical, normalized_payload)
        if payload_findings:
            return self._error_result(
                "Payload validation failed",
                findings=payload_findings,
            )

        try:
            entity = build_entity(canonical, normalized_payload)
            web = self._repo.load()
            new_web = getattr(web, spec.register_method)(entity)
            identifier = str(getattr(entity, "id"))
        except (EpistemicError, TypeError, ValueError) as exc:
            return self._error_result(str(exc))

        return self._finalize_mutation(
            operation="register",
            resource=canonical,
            identifier=identifier,
            new_web=new_web,
            dry_run=dry_run,
            message=f"Registered {canonical} {identifier}",
        )

    def get(self, resource: str, identifier: str) -> GatewayResult:
        """Retrieve a single resource by ID."""
        try:
            canonical = self.resolve_resource(resource)
            web = self._repo.load()
            entity = self._lookup_entity(web, canonical, identifier)
        except KeyError as exc:
            return self._error_result(str(exc))

        if entity is None:
            return self._error_result(f"{canonical} {identifier!r} does not exist")

        return GatewayResult(
            status="ok",
            changed=False,
            message=f"Retrieved {canonical} {identifier}",
            data={"resource": entity_to_dict(entity)},
        )

    def list(self, resource: str, **filters: object) -> GatewayResult:
        """List resources, optionally filtered."""
        try:
            canonical = self.resolve_resource(resource)
            spec = self._resource_spec(canonical)
            web = self._repo.load()
        except KeyError as exc:
            return self._error_result(str(exc))

        registry = getattr(web, spec.collection_attr)
        items = [
            entity_to_dict(entity)
            for _, entity in sorted(registry.items(), key=lambda item: str(item[0]))
        ]

        if filters:
            items = [
                item for item in items
                if self._matches_filters(item, filters)
            ]

        return GatewayResult(
            status="ok",
            changed=False,
            message=f"Listed {len(items)} {canonical} item(s)",
            data={"items": items, "count": len(items)},
        )

    def set(
        self,
        resource: str,
        identifier: str,
        payload: dict,
        *,
        dry_run: bool = False,
    ) -> GatewayResult:
        """Update fields on an existing resource."""
        try:
            canonical = self.resolve_resource(resource)
            spec = self._resource_spec(canonical)
            web = self._repo.load()
        except KeyError as exc:
            return self._error_result(str(exc))

        existing = self._lookup_entity(web, canonical, identifier)
        if existing is None:
            return self._error_result(f"{canonical} {identifier!r} does not exist")

        normalized_payload = normalize_payload(payload)
        incoming_identifier = normalized_payload.get("id")
        if incoming_identifier is not None and incoming_identifier != identifier:
            return self._error_result(
                f"Payload id {incoming_identifier!r} does not match {identifier!r}"
            )

        merged_payload = entity_to_dict(existing)
        merged_payload.update(normalized_payload)

        payload_findings = self._validate_payload(canonical, merged_payload)
        if payload_findings:
            return self._error_result(
                "Payload validation failed",
                findings=payload_findings,
            )

        try:
            entity = build_entity(canonical, merged_payload)
            new_web = getattr(web, spec.update_method)(entity)
        except (EpistemicError, TypeError, ValueError) as exc:
            return self._error_result(str(exc))

        return self._finalize_mutation(
            operation="set",
            resource=canonical,
            identifier=identifier,
            new_web=new_web,
            dry_run=dry_run,
            message=f"Updated {canonical} {identifier}",
        )

    def transition(
        self,
        resource: str,
        identifier: str,
        new_status: str,
        *,
        dry_run: bool = False,
    ) -> GatewayResult:
        """Transition a resource to a new status."""
        try:
            canonical = self.resolve_resource(resource)
            spec = self._resource_spec(canonical)
        except KeyError as exc:
            return self._error_result(str(exc))

        if spec.transition_method is None:
            return self._error_result(f"Resource {canonical!r} does not support transition")

        status_enum = status_enum_type(canonical)
        if status_enum is None:
            return self._error_result(f"Resource {canonical!r} does not define a status enum")

        try:
            web = self._repo.load()
            typed_identifier = self._typed_identifier(canonical, identifier)
            target_status = new_status
            if not isinstance(new_status, status_enum):
                target_status = status_enum(new_status)
            new_web = getattr(web, spec.transition_method)(typed_identifier, target_status)
        except (EpistemicError, TypeError, ValueError) as exc:
            return self._error_result(str(exc))

        return self._finalize_mutation(
            operation="transition",
            resource=canonical,
            identifier=identifier,
            new_web=new_web,
            dry_run=dry_run,
            message=(
                f"Transitioned {canonical} {identifier} to {serialize_value(target_status)}"
            ),
        )

    def query(self, query_type: str, **params: object) -> GatewayResult:
        """Run a named read-only query across the web."""
        query_spec = _QUERY_SPECS.get(query_type)
        if query_spec is None:
            return self._error_result(f"Unknown query type: {query_type!r}")

        missing = sorted(set(query_spec.parameter_resources) - set(params))
        if missing:
            return self._error_result(
                f"Missing query parameter(s) for {query_type!r}: {missing}"
            )

        unexpected = sorted(set(params) - set(query_spec.parameter_resources))
        if unexpected:
            return self._error_result(
                f"Unexpected query parameter(s) for {query_type!r}: {unexpected}"
            )

        try:
            web = self._repo.load()
            coerced_params = {
                name: self._typed_identifier(resource_name, str(params[name]))
                for name, resource_name in query_spec.parameter_resources.items()
            }
            result = getattr(web, query_spec.method_name)(**coerced_params)
        except (TypeError, ValueError) as exc:
            return self._error_result(str(exc))

        serialized = serialize_value(result)
        data = serialized if isinstance(serialized, dict) else {"result": serialized}

        return GatewayResult(
            status="ok",
            changed=False,
            message=f"Query {query_type} completed",
            data=data,
        )

    def _resource_spec(self, resource: str) -> _ResourceSpec:
        spec = _RESOURCE_SPECS.get(resource)
        if spec is None:
            raise KeyError(f"Unsupported resource type: {resource!r}")
        return spec

    def _typed_identifier(self, resource: str, identifier: str) -> object:
        return entity_id_type(resource)(identifier)

    def _lookup_entity(self, web, resource: str, identifier: str) -> object | None:
        spec = self._resource_spec(resource)
        registry = getattr(web, spec.collection_attr)
        return registry.get(self._typed_identifier(resource, identifier))

    def _validate_payload(self, resource: str, payload: dict[str, object]) -> list[Finding]:
        if self._payload_validator is None:
            return []
        return self._payload_validator.validate(resource, payload)

    def _finalize_mutation(
        self,
        *,
        operation: str,
        resource: str,
        identifier: str,
        new_web,
        dry_run: bool,
        message: str,
    ) -> GatewayResult:
        findings = self._validator.validate(new_web)
        critical_findings = [
            finding for finding in findings if finding.severity == Severity.CRITICAL
        ]
        if critical_findings:
            return GatewayResult(
                status="BLOCKED",
                changed=False,
                message="Mutation blocked by validation",
                findings=findings,
            )

        entity = self._lookup_entity(new_web, resource, identifier)
        data = {"resource": entity_to_dict(entity)} if entity is not None else None

        if dry_run:
            return GatewayResult(
                status="dry_run",
                changed=False,
                message=message,
                findings=findings,
                data=data,
            )

        self._repo.save(new_web)
        transaction_id = self._tx_log.append(f"{operation}:{resource}", identifier)
        return GatewayResult(
            status="ok",
            changed=True,
            message=message,
            findings=findings,
            transaction_id=transaction_id,
            data=data,
        )

    def _matches_filters(self, item: dict[str, object], filters: dict[str, object]) -> bool:
        for field_name, expected in filters.items():
            actual = item.get(field_name)
            normalized_expected = serialize_value(expected)
            if isinstance(actual, list):
                if isinstance(normalized_expected, list):
                    if not all(expected_item in actual for expected_item in normalized_expected):
                        return False
                    continue
                if normalized_expected not in actual:
                    return False
                continue
            if isinstance(actual, dict) and isinstance(normalized_expected, dict):
                for key, value in normalized_expected.items():
                    if actual.get(key) != value:
                        return False
                continue
            if actual != normalized_expected:
                return False
        return True

    def _error_result(
        self,
        message: str,
        *,
        findings: list[Finding] | None = None,
    ) -> GatewayResult:
        return GatewayResult(
            status="error",
            changed=False,
            message=message,
            findings=findings or [],
        )
