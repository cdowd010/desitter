"""Core client orchestration surface.

This module holds the shared client lifecycle, generic gateway verbs,
and internal result-handling helpers.
"""
from __future__ import annotations

from enum import Enum
from typing import Any

from ._types import ClientResult
from ..controlplane.gateway import Gateway, GatewayResult
from ..epistemic.codec import deserialize_entity
from ..epistemic.errors import EpistemicError
from ..epistemic.ports import GraphRepository


class _EpistemeClientCore:
    """Shared client lifecycle and generic gateway orchestration.

    Owns the ``Gateway`` reference and the optional ``GraphRepository``
    used for persistence. Provides the generic CRUD and query verbs
    (``register``, ``get``, ``list``, ``set``, ``transition``, ``query``)
    that typed helper methods delegate to.

    All public methods return ``ClientResult`` and never raise
    ``EpistemeClientError`` unless the gateway returns a non-success
    status and the caller has opted in to raising.
    """

    def __init__(
        self,
        gateway: Gateway,
        *,
        repo: GraphRepository | None = None,
    ) -> None:
        self._gateway = gateway
        self._repo = repo

    @property
    def gateway(self) -> Gateway:
        """The ``Gateway`` instance backing this client."""
        return self._gateway

    def save(self) -> None:
        """Persist the in-memory graph through the repository.

        A no-op when no repository was provided at construction time.
        Called automatically by ``__exit__`` when used as a context manager.
        """
        if self._repo is not None:
            self._repo.save(self._gateway.graph)

    def __enter__(self):
        return self

    def __exit__(self, *args: object) -> None:
        self.save()

    # ── Generic verbs ─────────────────────────────────────────────

    def register(
        self,
        resource: str,
        *,
        dry_run: bool = False,
        **payload: object,
    ) -> ClientResult[Any]:
        """Register a new resource entity using keyword arguments."""
        clean = {k: v for k, v in payload.items() if v is not None}
        result = self._invoke_gateway(self._gateway.register, resource, clean, dry_run=dry_run)
        return self._handle_resource_result(resource, result)

    def get(self, resource: str, identifier: str) -> ClientResult[Any]:
        """Retrieve a single resource entity by ID."""
        result = self._invoke_gateway(self._gateway.get, resource, identifier)
        return self._handle_resource_result(resource, result)

    def list(self, resource: str, **filters: object) -> ClientResult[list[Any]]:
        """List all entities of a resource type, optionally filtered."""
        result = self._invoke_gateway(self._gateway.list, resource, **filters)
        return self._handle_resource_list_result(resource, result)

    def set(
        self,
        resource: str,
        identifier: str,
        *,
        dry_run: bool = False,
        **payload: object,
    ) -> ClientResult[Any]:
        """Update fields on an existing resource entity."""
        clean = {k: v for k, v in payload.items() if v is not None}
        result = self._invoke_gateway(self._gateway.set, resource, identifier, clean, dry_run=dry_run)
        return self._handle_resource_result(resource, result)

    def transition(
        self,
        resource: str,
        identifier: str,
        new_status: str | Enum,
        *,
        dry_run: bool = False,
    ) -> ClientResult[Any]:
        """Transition a status-bearing resource entity to a new lifecycle state."""
        status_str = new_status.value if isinstance(new_status, Enum) else new_status
        result = self._invoke_gateway(
            self._gateway.transition, resource, identifier, status_str, dry_run=dry_run
        )
        return self._handle_resource_result(resource, result)

    def query(self, query_type: str, **params: object) -> ClientResult[Any]:
        """Run a named read-only gateway query."""
        result = self._invoke_gateway(self._gateway.query, query_type, **params)
        return self._handle_query_result(result)

    def validate(self, *, extra_validators=()) -> list:
        """Run domain validation against the current graph.

        Args:
            extra_validators: Additional ``GraphValidator`` instances to run
                alongside the built-in domain validator.

        Returns:
            list[Finding]: All findings from the domain validator and any
                extras.
        """
        findings = list(self._gateway.validate())
        for v in extra_validators:
            findings.extend(v.validate(self._gateway.graph))
        return findings

    # ── Private helpers ───────────────────────────────────────────

    def _invoke_gateway(self, func, *args, **kwargs) -> GatewayResult:
        """Call a gateway callable, wrapping unexpected exceptions."""
        try:
            return func(*args, **kwargs)
        except EpistemicError as exc:
            return GatewayResult(
                status="error",
                changed=False,
                message=str(exc),
            )
        except Exception as exc:  # noqa: BLE001
            return GatewayResult(
                status="error",
                changed=False,
                message=f"Unexpected error: {exc}",
            )

    def _handle_resource_result(
        self,
        resource: str,
        result: GatewayResult,
    ) -> ClientResult[Any]:
        """Convert a gateway result into a typed ``ClientResult``."""
        entity = None
        if result.status == "ok" and result.data is not None:
            raw = result.data.get("resource")
            if raw is not None:
                entity = deserialize_entity(resource, raw)
        return ClientResult(
            status=result.status,
            changed=result.changed,
            message=result.message,
            findings=result.findings,
            transaction_id=result.transaction_id,
            data=entity,
        )

    def _handle_resource_list_result(
        self,
        resource: str,
        result: GatewayResult,
    ) -> ClientResult[list[Any]]:
        """Convert a gateway list result into a typed ``ClientResult``."""
        items = None
        if result.status == "ok" and result.data is not None:
            raw_items = result.data.get("items", [])
            items = [deserialize_entity(resource, item) for item in raw_items]
        return ClientResult(
            status=result.status,
            changed=result.changed,
            message=result.message,
            findings=result.findings,
            transaction_id=result.transaction_id,
            data=items,
        )

    def _handle_query_result(self, result: GatewayResult) -> ClientResult[Any]:
        """Convert a gateway query result into a typed ``ClientResult``."""
        return ClientResult(
            status=result.status,
            changed=result.changed,
            message=result.message,
            findings=result.findings,
            transaction_id=result.transaction_id,
            data=result.data,
        )

    def _resource_key(self, resource: str) -> str:
        """Validate and return a canonical resource key."""
        return self._gateway.resolve_resource(resource)


__all__ = ["_EpistemeClientCore"]

