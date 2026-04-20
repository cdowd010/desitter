"""Core client orchestration surface.

This module holds the shared client lifecycle, generic gateway verbs,
and internal result-handling helpers.
"""
from __future__ import annotations

from enum import Enum
from typing import Any

from ._types import ClientResult
from ..controlplane.gateway import Gateway, GatewayResult
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
        """Initialize the client with a gateway and optional repository.

        Args:
            gateway: The ``Gateway`` instance that owns the in-memory graph
                and all mutation/query operations.
            repo: Optional ``GraphRepository`` used to persist the graph.
                When ``None``, ``save()`` is a no-op and the graph exists
                only in memory for the lifetime of the client.
        """
        raise NotImplementedError

    @property
    def gateway(self) -> Gateway:
        """The ``Gateway`` instance backing this client.

        Returns:
            Gateway: The gateway that owns the current in-memory graph.
        """
        raise NotImplementedError

    def save(self) -> None:
        """Persist the in-memory graph through the repository.

        A no-op when no repository was provided at construction time.
        Called automatically by ``__exit__`` when used as a context manager.
        """
        raise NotImplementedError

    def __enter__(self):
        """Enter the context manager.

        Returns:
            _EpistemeClientCore: ``self``, so that ``with ds.connect() as client:``
                binds the client to ``client``.
        """
        raise NotImplementedError

    def __exit__(self, *args: object) -> None:
        """Exit the context manager, calling ``save()`` on exit.

        Args:
            *args: Standard ``__exit__`` arguments (exc_type, exc_val,
                exc_tb). Exceptions are not suppressed.
        """
        raise NotImplementedError

    def register(
        self,
        resource: str,
        *,
        dry_run: bool = False,
        **payload: object,
    ) -> ClientResult[Any]:
        """Register a new resource entity using keyword arguments.

        Strips ``None`` values from ``payload``, then calls
        ``Gateway.register`` with the resulting dict.

        Args:
            resource: Canonical resource key (e.g. ``"claim"``).
            dry_run: When ``True``, validate without mutating the graph.
            **payload: Entity attributes as keyword arguments.

        Returns:
            ClientResult[Any]: Typed result with the registered entity
                in ``data`` on success.
        """
        raise NotImplementedError

    def get(self, resource: str, identifier: str) -> ClientResult[Any]:
        """Retrieve a single resource entity by ID.

        Args:
            resource: Canonical resource key (e.g. ``"prediction"``).
            identifier: String form of the entity's ID.

        Returns:
            ClientResult[Any]: Typed result with the entity in ``data``
                on success, or an error result if not found.
        """
        raise NotImplementedError

    def list(self, resource: str, **filters: object) -> ClientResult[list[Any]]:
        """List all entities of a resource type, optionally filtered.

        Args:
            resource: Canonical resource key (e.g. ``"assumption"``).
            **filters: Field-value pairs to match against serialized
                entity dicts.

        Returns:
            ClientResult[list[Any]]: Typed result with the matching
                entity list in ``data`` on success.
        """
        raise NotImplementedError

    def set(
        self,
        resource: str,
        identifier: str,
        *,
        dry_run: bool = False,
        **payload: object,
    ) -> ClientResult[Any]:
        """Update fields on an existing resource entity.

        Strips ``None`` values from ``payload`` before forwarding to
        ``Gateway.set``.

        Args:
            resource: Canonical resource key (e.g. ``"claim"``).
            identifier: String form of the entity's ID.
            dry_run: When ``True``, validate without mutating the graph.
            **payload: Fields to update as keyword arguments.

        Returns:
            ClientResult[Any]: Typed result with the updated entity
                in ``data`` on success.
        """
        raise NotImplementedError

    def transition(
        self,
        resource: str,
        identifier: str,
        new_status: str | Enum,
        *,
        dry_run: bool = False,
    ) -> ClientResult[Any]:
        """Transition a status-bearing resource entity to a new lifecycle state.

        Args:
            resource: Canonical resource key (e.g. ``"prediction"``).
            identifier: String form of the entity's ID.
            new_status: Target status value. Accepts the enum member itself
                or its string value.
            dry_run: When ``True``, validate without mutating the graph.

        Returns:
            ClientResult[Any]: Typed result with the updated entity
                in ``data`` on success, or an error result if the
                resource does not support transitions.
        """
        raise NotImplementedError

    def query(self, query_type: str, **params: object) -> ClientResult[Any]:
        """Run a named read-only gateway query.

        Args:
            query_type: One of the keys in ``QUERY_SPECS`` (e.g.
                ``"claim_lineage"``, ``"parameter_impact"``).
            **params: Named query parameters as declared by the
                ``QuerySpec`` (e.g. ``cid="C-001"``).

        Returns:
            ClientResult[Any]: Typed result with the serialized query
                output in ``data``, or an error result if the query
                type is unknown or a parameter is invalid.
        """
        raise NotImplementedError

    def _invoke_gateway(self, func, *args, **kwargs) -> GatewayResult:
        """Call a gateway callable, wrapping unexpected exceptions.

        Handles ``EpistemicError`` and any other unexpected exception,
        converting them to error ``GatewayResult`` instances so that all
        client-visible results remain typed rather than raised.

        Args:
            func: Callable to invoke (a bound gateway method).
            *args: Positional arguments to pass to ``func``.
            **kwargs: Keyword arguments to pass to ``func``.

        Returns:
            GatewayResult: The result from ``func``, or an error result
                if an exception was raised.
        """
        raise NotImplementedError

    def _handle_resource_result(
        self,
        resource: str,
        result: GatewayResult,
    ) -> ClientResult[Any]:
        """Convert a gateway result into a typed ``ClientResult``.

        Deserializes the entity from ``result.data[\"resource\"]`` into
        the appropriate typed domain class using the codec.

        Args:
            resource: Canonical resource key used for deserialization.
            result: The ``GatewayResult`` to convert.

        Returns:
            ClientResult[Any]: Typed result with the deserialized entity
                in ``data`` on success. On error, ``data`` is ``None``
                and the status/message/findings are forwarded.
        """
        raise NotImplementedError

    def _handle_resource_list_result(
        self,
        resource: str,
        result: GatewayResult,
    ) -> ClientResult[list[Any]]:
        """Convert a gateway list result into a typed ``ClientResult``.

        Deserializes each item from ``result.data[\"items\"]`` using the
        codec.

        Args:
            resource: Canonical resource key used for deserialization.
            result: The ``GatewayResult`` to convert.

        Returns:
            ClientResult[list[Any]]: Typed result with the deserialized
                entity list in ``data`` on success.
        """
        raise NotImplementedError

    def _handle_query_result(self, result: GatewayResult) -> ClientResult[Any]:
        """Convert a gateway query result into a typed ``ClientResult``.

        Query results are returned as raw data structures (sets, dicts of
        sets) without further deserialization; callers receive the
        primitive mapping directly.

        Args:
            result: The ``GatewayResult`` from a ``Gateway.query`` call.

        Returns:
            ClientResult[Any]: Typed result with the serialized query
                output as ``data``.
        """
        raise NotImplementedError

    def _resource_key(self, resource: str) -> str:
        """Validate and return a canonical resource key.

        Delegates to ``Gateway.resolve_resource``. Raises with a clear
        message if the key is not recognized.

        Args:
            resource: Raw resource name supplied by the caller.

        Returns:
            str: The canonical resource key.

        Raises:
            KeyError: If the resource is not in ``RESOURCE_SPECS``.
        """
        raise NotImplementedError


__all__ = ["_EpistemeClientCore"]
