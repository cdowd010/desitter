"""The single mutation/query boundary for the control plane.

Consumer adapters route all operations through the Gateway.

Responsibilities:
  - Hold an EpistemicGraphPort instance for the lifetime of a session.
    This may be in-memory (EpistemicGraph) or DB-backed (lazy-loading proxy).
  - Resource-oriented register/get/list/set/transition/query operations.
  - Payload parsing and normalization.
    - Resource key validation.
  - Dry-run semantics (validate without mutating).
  - Post-mutation invariant enforcement (CRITICAL findings block mutation).

Not responsible for:
  - Persistence. That belongs to EpistemeClient via GraphRepository.
  - Transaction logging. Deferred to the persistence layer.
  - Prose sync, view rendering, or any I/O.
  - Formatting human CLI output.
"""
from __future__ import annotations

from collections.abc import Mapping

from ._gateway_catalog import QUERY_SPECS, RESOURCE_SPECS, QuerySpec, ResourceSpec
from ._gateway_results import GatewayResult
from ..epistemic.codec import (
    entity_id_type,
    entity_to_dict,
    normalize_payload,
    serialize_value,
    status_enum_type,
)
from ..epistemic.ports import (
    EpistemicGraphPort,
    PayloadValidator,
    GraphValidator,
)
from ..epistemic.types import Finding, Severity
from ..epistemic.errors import EpistemicError


class Gateway:
    """Single mutation/query boundary for the control plane.

    Holds a reference to an ``EpistemicGraphPort`` instance for the session
    lifetime. This may be a concrete ``EpistemicGraph`` (in-memory) or a
    DB-backed proxy implementing the same protocol. Either way, the Gateway
    treats it identically via the protocol.

    Every public method returns a ``GatewayResult`` and never raises.
    Persistence is the caller's responsibility (``EpistemeClient.save()``).
    """

    def __init__(
        self,
        graph: EpistemicGraphPort,
        validator: GraphValidator,
        payload_validator: PayloadValidator | None = None,
    ) -> None:
        """Initialize a gateway with an epistemic graph instance.

        Args:
            graph: Any ``EpistemicGraphPort`` implementation. Typically a concrete
                ``EpistemicGraph()`` for in-memory sessions or a pre-loaded graph
                from a ``GraphRepository`` (JSON, DB-backed, etc.) for persistent
                sessions. The Gateway treats all implementations identically.
            validator: Domain validation service (invariant checks).
            payload_validator: Optional schema validator for incoming
                payloads. If ``None``, schema validation is skipped.
        """
        raise NotImplementedError

    @property
    def graph(self) -> EpistemicGraphPort:
        """The current in-memory epistemic graph."""
        raise NotImplementedError

    def resolve_resource(self, resource: str) -> str:
        """Validate and return a canonical resource key.

        Args:
            resource: Canonical resource key such as ``"hypothesis"`` or
                ``"dead_end"``.

        Returns:
            str: The same canonical resource key.

        Raises:
            KeyError: If the resource is not supported.
        """
        raise NotImplementedError

    def register(
        self,
        resource: str,
        payload: Mapping[str, object],
        *,
        dry_run: bool = False,
    ) -> GatewayResult:
        """Register a new resource entity.

        Validates payload, builds entity, registers on the in-memory graph,
        enforces domain invariants. Updates ``self._graph`` on success.

        Args:
            resource: Canonical resource key.
            payload: Entity attributes as a primitive mapping.
            dry_run: If ``True``, validate without mutating the graph.

        Returns:
            GatewayResult: ``"ok"`` on success, ``"BLOCKED"`` on invariant
                failure, ``"error"`` on bad input.
        """
        raise NotImplementedError

    def get(self, resource: str, identifier: str) -> GatewayResult:
        """Retrieve a single resource entity by ID.

        Args:
            resource: Canonical resource key.
            identifier: String form of the entity's ID.

        Returns:
            GatewayResult: ``data["resource"]`` is the serialized entity
                on success, or ``status="error"`` if not found.
        """
        raise NotImplementedError

    def list(self, resource: str, **filters: object) -> GatewayResult:
        """List all entities of a resource type, optionally filtered.

        Entities are sorted by ID for deterministic output. Filters use
        list-contains, dict-subset, or scalar-equality semantics.

        Args:
            resource: Canonical resource key.
            **filters: Field-value pairs to match.

        Returns:
            GatewayResult: ``data["items"]`` is the matching entity list;
                ``data["count"]`` is the total.
        """
        raise NotImplementedError

    def set(
        self,
        resource: str,
        identifier: str,
        payload: Mapping[str, object],
        *,
        dry_run: bool = False,
    ) -> GatewayResult:
        """Update fields on an existing resource entity.

        Merges ``payload`` onto the existing serialized entity, validates
        the merged result, and updates the in-memory graph on success.

        Args:
            resource: Canonical resource key.
            identifier: String form of the entity's ID.
            payload: Partial entity attributes to apply.
            dry_run: If ``True``, validate without mutating the graph.

        Returns:
            GatewayResult: ``"ok"`` on success, ``"BLOCKED"`` on invariant
                failure, ``"error"`` on bad input.
        """
        raise NotImplementedError

    def transition(
        self,
        resource: str,
        identifier: str,
        new_status: str,
        *,
        dry_run: bool = False,
    ) -> GatewayResult:
        """Transition a resource entity to a new status.

        Args:
            resource: Canonical resource key.
            identifier: String form of the entity's ID.
            new_status: Target status value (matched against the
                resource's status enum).
            dry_run: If ``True``, validate without mutating the graph.

        Returns:
            GatewayResult: ``"ok"`` on success, ``"error"`` if the
                resource does not support transitions.
        """
        raise NotImplementedError

    def query(self, query_type: str, **params: object) -> GatewayResult:
        """Run a named read-only query across the epistemic graph.

        Args:
            query_type: One of the keys in ``QUERY_SPECS``.
            **params: Named query parameters matching the spec.

        Returns:
            GatewayResult: ``data`` holds the serialized query result.
                ``status="error"`` if query type is unknown.
        """
        raise NotImplementedError

    # ── Private helpers ───────────────────────────────────────────

    def _resource_spec(self, resource: str) -> ResourceSpec:
        """Look up the ``ResourceSpec`` for a canonical resource key.

        Args:
            resource: Canonical resource key (e.g. ``"hypothesis"``).

        Returns:
            ResourceSpec: The metadata descriptor for the resource.

        Raises:
            KeyError: If ``resource`` is not in ``RESOURCE_SPECS``.
        """
        raise NotImplementedError

    def _typed_identifier(self, resource: str, identifier: str) -> object:
        """Coerce a string identifier to the resource's typed ID NewType.

        Args:
            resource: Canonical resource key (e.g. ``"hypothesis"``).
            identifier: Raw string form of the entity ID.

        Returns:
            object: The typed NewType instance (e.g. ``HypothesisId("C-001")``).

        Raises:
            KeyError: If ``resource`` is not recognized.
        """
        raise NotImplementedError

    def _lookup_entity(self, resource: str, identifier: str) -> object | None:
        """Find an entity in the in-memory graph by resource key and string ID.

        Args:
            resource: Canonical resource key (e.g. ``"prediction"``).
            identifier: Raw string form of the entity ID.

        Returns:
            object | None: The domain entity instance, or ``None`` if the
                entity does not exist in the graph.
        """
        raise NotImplementedError

    def _validate_payload(
        self,
        resource: str,
        payload: Mapping[str, object],
    ) -> list[Finding]:
        """Run schema validation if a ``PayloadValidator`` is configured.

        When no ``PayloadValidator`` was injected at construction time,
        returns an empty list (validation is skipped).

        Args:
            resource: Canonical resource key (e.g. ``"hypothesis"``).
            payload: Inbound mutation payload to validate.

        Returns:
            list[Finding]: Zero or more schema findings. Empty when
                no validator is configured or no issues are found.
        """
        raise NotImplementedError

    def _finalize_mutation(
        self,
        *,
        operation: str,
        resource: str,
        identifier: str,
        new_graph: EpistemicGraphPort,
        dry_run: bool,
        message: str,
    ) -> GatewayResult:
        """Enforce invariants and, if clean, commit the new graph to memory.

        Runs the ``GraphValidator`` against ``new_graph``. If any CRITICAL
        findings are produced, returns a ``BLOCKED`` result without
        updating ``self._graph``. If ``dry_run`` is ``True``, validates
        but does not update ``self._graph`` regardless of findings.
        Otherwise sets ``self._graph = new_graph``.

        Persistence (``repo.save()``) is NOT performed here. That
        belongs to ``EpistemeClient.save()``.

        Args:
            operation: Human-readable operation name for the result message.
            resource: Canonical resource key (used in log/message context).
            identifier: The entity ID affected by the operation.
            new_graph: The candidate new graph state produced by the mutation.
            dry_run: When ``True``, validate without committing the new graph.
            message: Success message to include in the result when no
                CRITICAL findings are present.

        Returns:
            GatewayResult: ``"ok"`` with ``changed=True`` on clean commit;
                ``"ok"`` with ``changed=False`` on a clean dry_run;
                ``"BLOCKED"`` if any CRITICAL findings were produced.
        """
        raise NotImplementedError

    def _matches_filters(
        self,
        item: Mapping[str, object],
        filters: Mapping[str, object],
    ) -> bool:
        """Test whether a serialized entity dict matches all filter predicates.

        Matching semantics per field type:
        - ``list`` field vs filter value: field must contain the value.
        - ``dict`` field vs filter value: field must be a superset of the
          filter mapping.
        - Scalar field: equality comparison.

        Args:
            item: Serialized entity dict (the candidate to test).
            filters: Key-value pairs that must all match for the item
                to be included.

        Returns:
            bool: ``True`` if every filter predicate matches the item.
        """
        raise NotImplementedError

    def _error_result(
        self,
        message: str,
        *,
        findings: list[Finding] | None = None,
    ) -> GatewayResult:
        """Construct an error ``GatewayResult``.

        Args:
            message: Human-readable error description.
            findings: Optional structured findings to include alongside
                the error message (e.g. schema violations).

        Returns:
            GatewayResult: Result with ``status="error"``,
                ``changed=False``, and the provided message and findings.
        """
        raise NotImplementedError

