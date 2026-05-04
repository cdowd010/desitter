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
    build_entity,
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
    TransactionLog,
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
        transaction_log: TransactionLog | None = None,
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
        self._graph = graph
        self._validator = validator
        self._payload_validator = payload_validator
        self._transaction_log = transaction_log

    @property
    def graph(self) -> EpistemicGraphPort:
        """The current in-memory epistemic graph."""
        return self._graph

    def validate(self) -> list[Finding]:
        """Run domain validation against the current in-memory graph.

        Returns:
            list[Finding]: All findings from the domain validator.
        """
        return self._validator.validate(self._graph)

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
        if resource not in RESOURCE_SPECS:
            raise KeyError(f"Unknown resource: {resource}")
        return resource

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
        try:
            self.resolve_resource(resource)
        except KeyError as exc:
            return self._error_result(str(exc))

        findings = self._validate_payload(resource, payload)
        critical = [f for f in findings if f.severity == Severity.CRITICAL]
        if critical:
            return GatewayResult(
                status="error",
                changed=False,
                message="Payload validation failed",
                findings=findings,
            )

        try:
            entity = build_entity(resource, payload)
        except (KeyError, TypeError, ValueError) as exc:
            return self._error_result(f"Invalid payload: {exc}")

        spec = self._resource_spec(resource)
        try:
            new_graph = getattr(self._graph, spec.register_method)(entity)
        except EpistemicError as exc:
            return self._error_result(str(exc))

        identifier = str(payload.get("id", ""))
        return self._finalize_mutation(
            operation=f"register_{resource}",
            resource=resource,
            identifier=identifier,
            new_graph=new_graph,
            dry_run=dry_run,
            message=f"Registered {resource} {identifier!r}",
        )

    def get(self, resource: str, identifier: str) -> GatewayResult:
        """Retrieve a single resource entity by ID.

        Args:
            resource: Canonical resource key.
            identifier: String form of the entity's ID.

        Returns:
            GatewayResult: ``data["resource"]`` is the serialized entity
                on success, or ``status="error"`` if not found.
        """
        try:
            self.resolve_resource(resource)
        except KeyError as exc:
            return self._error_result(str(exc))

        entity = self._lookup_entity(resource, identifier)
        if entity is None:
            return self._error_result(f"{resource} {identifier!r} not found")

        return GatewayResult(
            status="ok",
            changed=False,
            message=f"Found {resource} {identifier!r}",
            data={"resource": entity_to_dict(entity)},
        )

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
        try:
            self.resolve_resource(resource)
        except KeyError as exc:
            return self._error_result(str(exc))

        spec = self._resource_spec(resource)
        collection = getattr(self._graph, spec.collection_attr)

        items = sorted(
            [entity_to_dict(entity) for entity in collection.values()],
            key=lambda d: str(d.get("id", "")),
        )

        if filters:
            items = [item for item in items if self._matches_filters(item, filters)]

        return GatewayResult(
            status="ok",
            changed=False,
            message=f"Listed {len(items)} {resource}(s)",
            data={"items": items, "count": len(items)},
        )

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
        try:
            self.resolve_resource(resource)
        except KeyError as exc:
            return self._error_result(str(exc))

        entity = self._lookup_entity(resource, identifier)
        if entity is None:
            return self._error_result(f"{resource} {identifier!r} not found")

        merged = {**entity_to_dict(entity), **normalize_payload(payload)}

        findings = self._validate_payload(resource, merged)
        critical = [f for f in findings if f.severity == Severity.CRITICAL]
        if critical:
            return GatewayResult(
                status="error",
                changed=False,
                message="Payload validation failed",
                findings=findings,
            )

        try:
            updated = build_entity(resource, merged)
        except (KeyError, TypeError, ValueError) as exc:
            return self._error_result(f"Invalid payload: {exc}")

        spec = self._resource_spec(resource)
        try:
            new_graph = getattr(self._graph, spec.update_method)(updated)
        except EpistemicError as exc:
            return self._error_result(str(exc))

        return self._finalize_mutation(
            operation=f"update_{resource}",
            resource=resource,
            identifier=identifier,
            new_graph=new_graph,
            dry_run=dry_run,
            message=f"Updated {resource} {identifier!r}",
        )

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
        try:
            self.resolve_resource(resource)
        except KeyError as exc:
            return self._error_result(str(exc))

        spec = self._resource_spec(resource)
        if spec.transition_method is None:
            return self._error_result(f"{resource!r} does not support status transitions")

        entity = self._lookup_entity(resource, identifier)
        if entity is None:
            return self._error_result(f"{resource} {identifier!r} not found")

        status_cls = status_enum_type(resource)
        try:
            target_status = status_cls(new_status)
        except ValueError:
            return self._error_result(f"Invalid status {new_status!r} for {resource}")

        typed_id = self._typed_identifier(resource, identifier)
        try:
            new_graph = getattr(self._graph, spec.transition_method)(typed_id, target_status)
        except EpistemicError as exc:
            return self._error_result(str(exc))

        return self._finalize_mutation(
            operation=f"transition_{resource}",
            resource=resource,
            identifier=identifier,
            new_graph=new_graph,
            dry_run=dry_run,
            message=f"Transitioned {resource} {identifier!r} to {new_status!r}",
        )

    def query(self, query_type: str, **params: object) -> GatewayResult:
        """Run a named read-only query across the epistemic graph.

        Args:
            query_type: One of the keys in ``QUERY_SPECS``.
            **params: Named query parameters matching the spec.

        Returns:
            GatewayResult: ``data`` holds the serialized query result.
                ``status="error"`` if query type is unknown.
        """
        if query_type not in QUERY_SPECS:
            return self._error_result(f"Unknown query type: {query_type!r}")

        spec = QUERY_SPECS[query_type]

        coerced: dict[str, object] = {}
        for key, value in params.items():
            res = spec.parameter_resources.get(key)
            if res is not None:
                coerced[key] = entity_id_type(res)(value)
            else:
                coerced[key] = value

        try:
            result = getattr(self._graph, spec.method_name)(**coerced)
        except EpistemicError as exc:
            return self._error_result(str(exc))

        return GatewayResult(
            status="ok",
            changed=False,
            message=f"Query {query_type!r} completed",
            data={"result": serialize_value(result)},
        )

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
        return RESOURCE_SPECS[resource]

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
        id_constructor = entity_id_type(resource)
        return id_constructor(identifier)

    def _lookup_entity(self, resource: str, identifier: str) -> object | None:
        """Find an entity in the in-memory graph by resource key and string ID.

        Args:
            resource: Canonical resource key (e.g. ``"prediction"``).
            identifier: Raw string form of the entity ID.

        Returns:
            object | None: The domain entity instance, or ``None`` if the
                entity does not exist in the graph.
        """
        spec = self._resource_spec(resource)
        collection = getattr(self._graph, spec.collection_attr)
        typed_id = self._typed_identifier(resource, identifier)
        return collection.get(typed_id)

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
        if self._payload_validator is None:
            return []
        return self._payload_validator.validate(resource, payload)

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
        findings = self._validator.validate(new_graph)
        critical = [f for f in findings if f.severity == Severity.CRITICAL]
        if critical:
            return GatewayResult(
                status="BLOCKED",
                changed=False,
                message=f"Mutation blocked: {len(critical)} CRITICAL finding(s)",
                findings=findings,
            )
        if not dry_run:
            self._graph = new_graph
        # Hydrate the result with the entity from the post-mutation graph so
        # that client callers receive the typed entity without a second round-trip.
        spec = self._resource_spec(resource)
        collection = getattr(new_graph, spec.collection_attr)
        typed_id = self._typed_identifier(resource, identifier)
        entity = collection.get(typed_id)
        data = {"resource": entity_to_dict(entity)} if entity is not None else None
        transaction_id: str | None = None
        if not dry_run and self._transaction_log is not None:
            transaction_id = self._transaction_log.append(operation, identifier)
        return GatewayResult(
            status="ok",
            changed=not dry_run,
            message=message,
            findings=findings,
            transaction_id=transaction_id,
            data=data,
        )

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
        for key, expected in filters.items():
            actual = item.get(key)
            if isinstance(actual, list):
                if expected not in actual:
                    return False
            elif isinstance(actual, dict):
                if not isinstance(expected, dict):
                    return False
                if not all(actual.get(k) == v for k, v in expected.items()):
                    return False
            else:
                if actual != expected:
                    return False
        return True

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
        return GatewayResult(
            status="error",
            changed=False,
            message=message,
            findings=findings or [],
        )

