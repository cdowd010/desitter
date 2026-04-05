"""Python client API for deSitter.

This module is a thin wrapper over the Gateway. It changes calling
conventions and result ergonomics only; all mutations still flow through
the same gateway, repository, validator, and transaction log.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Any, Generic, Iterable, Mapping, TypeVar, cast

from .config import ProjectContext, build_context, load_config
from .controlplane.factory import build_gateway
from .controlplane.gateway import Gateway, GatewayResult
from .epistemic.codec import deserialize_entity
from .epistemic.model import (
    Analysis,
    Assumption,
    Claim,
    DeadEnd,
    Discovery,
    IndependenceGroup,
    PairwiseSeparation,
    Parameter,
    Prediction,
    Theory,
)
from .epistemic.types import (
    AssumptionType,
    ClaimCategory,
    ClaimStatus,
    ClaimType,
    ConfidenceTier,
    DeadEndStatus,
    DiscoveryStatus,
    EvidenceKind,
    Finding,
    MeasurementRegime,
    PredictionStatus,
    TheoryStatus,
)


ResultData = TypeVar("ResultData")


@dataclass(frozen=True)
class ClientResult(Generic[ResultData]):
    """Typed wrapper over a ``GatewayResult``.

    Provides the same status/changed/message contract as ``GatewayResult``
    but with a typed ``data`` field that holds a deserialized domain entity
    (or list of entities) instead of a raw dict.

    Attributes:
        status: One of ``"ok"``, ``"dry_run"``, etc.
        changed: ``True`` if persistent state was modified.
        message: Human-readable summary.
        findings: Validation findings (may be empty).
        transaction_id: UUID4 if the operation was persisted.
        data: The deserialized result, or ``None``.
    """

    status: str
    changed: bool
    message: str
    findings: list[Finding] = field(default_factory=list)
    transaction_id: str | None = None
    data: ResultData | None = None


class DeSitterClientError(Exception):
    """Raised when the gateway returns a non-success status.

    Attributes:
        status: The gateway status string (e.g. ``"error"``, ``"BLOCKED"``).
        message: Human-readable error message.
        findings: Validation findings associated with the failure.
    """

    def __init__(
        self,
        status: str,
        message: str,
        findings: list[Finding] | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.message = message
        self.findings = findings or []


class DeSitterClient:
    """Thin Python wrapper over the gateway boundary.

    Provides typed convenience methods for every resource type so that
    callers can use keyword arguments and receive deserialized domain
    objects instead of raw dicts. All mutations still flow through the
    same Gateway, repository, validator, and transaction log.

    Attributes:
        _context: Project runtime context.
        _gateway: The ``Gateway`` instance backing all operations.
    """

    def __init__(self, context: ProjectContext, gateway: Gateway | None = None) -> None:
        """Initialize a client.

        Args:
            context: Project runtime context.
            gateway: Optional pre-built gateway. If ``None``, one is
                constructed from the context.
        """
        self._context = context
        self._gateway = gateway or build_gateway(context)

    @property
    def context(self) -> ProjectContext:
        """The runtime context used by this client."""
        return self._context

    @property
    def gateway(self) -> Gateway:
        """The gateway instance backing this client."""
        return self._gateway

    def register(
        self,
        resource: str,
        *,
        dry_run: bool = False,
        **payload: object,
    ) -> ClientResult[Any]:
        """Register a new resource using keyword arguments instead of a raw dict.

        Args:
            resource: Resource alias or canonical key.
            dry_run: If ``True``, validate without writing to disk.
            **payload: Entity attributes as keyword arguments.

        Returns:
            ClientResult: Deserialized entity in ``data`` on success.

        Raises:
            DeSitterClientError: If the gateway returns a non-success status.
        """
        return self._handle_resource_result(
            resource,
            self._invoke_gateway(
                self._gateway.register,
                resource,
                payload,
                dry_run=dry_run,
            ),
        )

    def get(self, resource: str, identifier: str) -> ClientResult[Any]:
        """Retrieve a single resource by ID.

        Args:
            resource: Resource alias or canonical key.
            identifier: The entity's string ID.

        Returns:
            ClientResult: Deserialized entity in ``data``.

        Raises:
            DeSitterClientError: If the entity does not exist.
        """
        return self._handle_resource_result(
            resource,
            self._invoke_gateway(self._gateway.get, resource, identifier),
        )

    def list(self, resource: str, **filters: object) -> ClientResult[list[Any]]:
        """List resources, optionally filtering by keyword arguments.

        Args:
            resource: Resource alias or canonical key.
            **filters: Field-value pairs to match.

        Returns:
            ClientResult: ``data`` is a list of deserialized entities.

        Raises:
            DeSitterClientError: If the gateway returns a non-success status.
        """
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
        """Update a resource using keyword arguments instead of a raw dict.

        Args:
            resource: Resource alias or canonical key.
            identifier: The entity's string ID.
            dry_run: If ``True``, validate without writing to disk.
            **payload: Fields to update.

        Returns:
            ClientResult: Updated deserialized entity in ``data``.

        Raises:
            DeSitterClientError: If the entity does not exist or validation fails.
        """
        return self._handle_resource_result(
            resource,
            self._invoke_gateway(
                self._gateway.set,
                resource,
                identifier,
                payload,
                dry_run=dry_run,
            ),
        )

    def transition(
        self,
        resource: str,
        identifier: str,
        new_status: str | Enum,
        *,
        dry_run: bool = False,
    ) -> ClientResult[Any]:
        """Transition a status-bearing resource to a new state.

        Args:
            resource: Resource alias or canonical key.
            identifier: The entity's string ID.
            new_status: Target status value (string or enum member).
            dry_run: If ``True``, validate without writing to disk.

        Returns:
            ClientResult: Updated deserialized entity in ``data``.

        Raises:
            DeSitterClientError: If the transition is invalid.
        """
        return self._handle_resource_result(
            resource,
            self._invoke_gateway(
                self._gateway.transition,
                resource,
                identifier,
                new_status,
                dry_run=dry_run,
            ),
        )

    def query(self, query_type: str, **params: object) -> ClientResult[Any]:
        """Run a named gateway query.

        Args:
            query_type: Query name (e.g. ``"claim_lineage"``).
            **params: Query parameters.

        Returns:
            ClientResult: Query result in ``data``.

        Raises:
            DeSitterClientError: If the query fails.
        """
        result = self._invoke_gateway(self._gateway.query, query_type, **params)
        return self._handle_query_result(result)

    def register_claim(
        self,
        id: str,
        statement: str,
        type: ClaimType | str,
        scope: str,
        falsifiability: str,
        *,
        dry_run: bool = False,
        status: ClaimStatus | str | None = None,
        category: ClaimCategory | str | None = None,
        assumptions: Iterable[str] | None = None,
        depends_on: Iterable[str] | None = None,
        analyses: Iterable[str] | None = None,
        parameter_constraints: Mapping[str, str] | None = None,
        source: str | None = None,
    ) -> ClientResult[Claim]:
        """Register a claim with typed keyword arguments.

        Convenience wrapper over ``register("claim", ...)`` that provides
        type-safe parameters and elides ``None`` values from the payload.

        Args:
            id: Unique claim identifier.
            statement: The claim statement.
            type: Claim type (qualitative, numerical, etc.).
            scope: Scope description.
            falsifiability: How the claim can be falsified.
            dry_run: If ``True``, validate without persisting.
            status: Initial status. Defaults to ``ACTIVE``.
            category: Optional category.
            assumptions: IDs of assumptions this claim relies on.
            depends_on: IDs of parent claims in the dependency graph.
            analyses: IDs of analyses supporting this claim.
            parameter_constraints: Parameter name → constraint mappings.
            source: Provenance reference.

        Returns:
            ClientResult[Claim]: The registered claim entity.
        """
        return cast(
            ClientResult[Claim],
            self.register(
                "claim",
                dry_run=dry_run,
                **_without_none(
                    id=id,
                    statement=statement,
                    type=type,
                    scope=scope,
                    falsifiability=falsifiability,
                    status=status,
                    category=category,
                    assumptions=list(assumptions) if assumptions is not None else None,
                    depends_on=list(depends_on) if depends_on is not None else None,
                    analyses=list(analyses) if analyses is not None else None,
                    parameter_constraints=dict(parameter_constraints)
                    if parameter_constraints is not None else None,
                    source=source,
                ),
            ),
        )

    def register_assumption(
        self,
        id: str,
        statement: str,
        type: AssumptionType | str,
        scope: str,
        *,
        dry_run: bool = False,
        depends_on: Iterable[str] | None = None,
        falsifiable_consequence: str | None = None,
        source: str | None = None,
        notes: str | None = None,
    ) -> ClientResult[Assumption]:
        """Register an assumption with typed keyword arguments.

        Args:
            id: Unique assumption identifier.
            statement: The assumption statement.
            type: Assumption type (empirical, mathematical, etc.).
            scope: Scope description.
            dry_run: If ``True``, validate without persisting.
            depends_on: IDs of parent assumptions.
            falsifiable_consequence: Description of a testable consequence.
            source: Provenance reference.
            notes: Free-form notes.

        Returns:
            ClientResult[Assumption]: The registered assumption entity.
        """
        return cast(
            ClientResult[Assumption],
            self.register(
                "assumption",
                dry_run=dry_run,
                **_without_none(
                    id=id,
                    statement=statement,
                    type=type,
                    scope=scope,
                    depends_on=list(depends_on) if depends_on is not None else None,
                    falsifiable_consequence=falsifiable_consequence,
                    source=source,
                    notes=notes,
                ),
            ),
        )

    def register_prediction(
        self,
        id: str,
        observable: str,
        tier: ConfidenceTier | str,
        status: PredictionStatus | str,
        evidence_kind: EvidenceKind | str,
        measurement_regime: MeasurementRegime | str,
        predicted: object,
        *,
        dry_run: bool = False,
        specification: str | None = None,
        derivation: str | None = None,
        claim_ids: Iterable[str] | None = None,
        tests_assumptions: Iterable[str] | None = None,
        analysis: str | None = None,
        independence_group: str | None = None,
        correlation_tags: Iterable[str] | None = None,
        observed: object | None = None,
        observed_bound: object | None = None,
        free_params: int | None = None,
        conditional_on: Iterable[str] | None = None,
        falsifier: str | None = None,
        benchmark_source: str | None = None,
        source: str | None = None,
        notes: str | None = None,
    ) -> ClientResult[Prediction]:
        """Register a prediction with typed keyword arguments.

        Args:
            id: Unique prediction identifier.
            observable: The observable quantity being predicted.
            tier: Confidence tier (A, B, or C).
            status: Initial prediction status.
            evidence_kind: Kind of evidence (measurement, simulation, etc.).
            measurement_regime: Regime classification.
            predicted: The predicted numerical value or range.
            dry_run: If ``True``, validate without persisting.
            specification: Detailed prediction specification.
            derivation: Derivation steps or reference.
            claim_ids: IDs of claims this prediction tests.
            tests_assumptions: IDs of assumptions this prediction tests.
            analysis: ID of the analysis producing this prediction.
            independence_group: ID of the independence group.
            correlation_tags: Tags marking correlated measurement channels.
            observed: Observed value, if available.
            observed_bound: Observed bound, if applicable.
            free_params: Number of free parameters in the prediction.
            conditional_on: IDs of assumptions this is conditional on.
            falsifier: ID of the prediction that falsified this one.
            benchmark_source: Benchmark reference.
            source: Provenance reference.
            notes: Free-form notes.

        Returns:
            ClientResult[Prediction]: The registered prediction entity.
        """
        return cast(
            ClientResult[Prediction],
            self.register(
                "prediction",
                dry_run=dry_run,
                **_without_none(
                    id=id,
                    observable=observable,
                    tier=tier,
                    status=status,
                    evidence_kind=evidence_kind,
                    measurement_regime=measurement_regime,
                    predicted=predicted,
                    specification=specification,
                    derivation=derivation,
                    claim_ids=list(claim_ids) if claim_ids is not None else None,
                    tests_assumptions=list(tests_assumptions)
                    if tests_assumptions is not None else None,
                    analysis=analysis,
                    independence_group=independence_group,
                    correlation_tags=list(correlation_tags)
                    if correlation_tags is not None else None,
                    observed=observed,
                    observed_bound=observed_bound,
                    free_params=free_params,
                    conditional_on=list(conditional_on)
                    if conditional_on is not None else None,
                    falsifier=falsifier,
                    benchmark_source=benchmark_source,
                    source=source,
                    notes=notes,
                ),
            ),
        )

    def register_analysis(
        self,
        id: str,
        *,
        dry_run: bool = False,
        command: str | None = None,
        path: str | None = None,
        uses_parameters: Iterable[str] | None = None,
        notes: str | None = None,
        last_result: object | None = None,
        last_result_sha: str | None = None,
        last_result_date: date | str | None = None,
    ) -> ClientResult[Analysis]:
        """Register an analysis with typed keyword arguments.

        Args:
            id: Unique analysis identifier.
            dry_run: If ``True``, validate without persisting.
            command: Shell command that runs the analysis.
            path: Filesystem path to the analysis script.
            uses_parameters: IDs of parameters consumed by this analysis.
            notes: Free-form notes.
            last_result: Most recent result value.
            last_result_sha: SHA of the last result for staleness detection.
            last_result_date: Date of the last result.

        Returns:
            ClientResult[Analysis]: The registered analysis entity.
        """
        return cast(
            ClientResult[Analysis],
            self.register(
                "analysis",
                dry_run=dry_run,
                **_without_none(
                    id=id,
                    command=command,
                    path=path,
                    uses_parameters=list(uses_parameters)
                    if uses_parameters is not None else None,
                    notes=notes,
                    last_result=last_result,
                    last_result_sha=last_result_sha,
                    last_result_date=last_result_date,
                ),
            ),
        )

    def register_theory(
        self,
        id: str,
        title: str,
        status: TheoryStatus | str,
        *,
        dry_run: bool = False,
        summary: str | None = None,
        related_claims: Iterable[str] | None = None,
        related_predictions: Iterable[str] | None = None,
        source: str | None = None,
    ) -> ClientResult[Theory]:
        """Register a theory with typed keyword arguments.

        Args:
            id: Unique theory identifier.
            title: Display title.
            status: Theory status (proposed, active, etc.).
            dry_run: If ``True``, validate without persisting.
            summary: Summary description.
            related_claims: IDs of related claims.
            related_predictions: IDs of related predictions.
            source: Provenance reference.

        Returns:
            ClientResult[Theory]: The registered theory entity.
        """
        return cast(
            ClientResult[Theory],
            self.register(
                "theory",
                dry_run=dry_run,
                **_without_none(
                    id=id,
                    title=title,
                    status=status,
                    summary=summary,
                    related_claims=list(related_claims)
                    if related_claims is not None else None,
                    related_predictions=list(related_predictions)
                    if related_predictions is not None else None,
                    source=source,
                ),
            ),
        )

    def register_discovery(
        self,
        id: str,
        title: str,
        date: date | str,
        summary: str,
        impact: str,
        status: DiscoveryStatus | str,
        *,
        dry_run: bool = False,
        related_claims: Iterable[str] | None = None,
        related_predictions: Iterable[str] | None = None,
        references: Iterable[str] | None = None,
        source: str | None = None,
    ) -> ClientResult[Discovery]:
        """Register a discovery with typed keyword arguments.

        Args:
            id: Unique discovery identifier.
            title: Display title.
            date: Discovery date.
            summary: Summary description.
            impact: Impact assessment.
            status: Discovery status.
            dry_run: If ``True``, validate without persisting.
            related_claims: IDs of related claims.
            related_predictions: IDs of related predictions.
            references: External reference strings.
            source: Provenance reference.

        Returns:
            ClientResult[Discovery]: The registered discovery entity.
        """
        return cast(
            ClientResult[Discovery],
            self.register(
                "discovery",
                dry_run=dry_run,
                **_without_none(
                    id=id,
                    title=title,
                    date=date,
                    summary=summary,
                    impact=impact,
                    status=status,
                    related_claims=list(related_claims)
                    if related_claims is not None else None,
                    related_predictions=list(related_predictions)
                    if related_predictions is not None else None,
                    references=list(references) if references is not None else None,
                    source=source,
                ),
            ),
        )

    def register_dead_end(
        self,
        id: str,
        title: str,
        description: str,
        status: DeadEndStatus | str,
        *,
        dry_run: bool = False,
        related_predictions: Iterable[str] | None = None,
        related_claims: Iterable[str] | None = None,
        references: Iterable[str] | None = None,
        source: str | None = None,
    ) -> ClientResult[DeadEnd]:
        """Register a dead end with typed keyword arguments.

        Args:
            id: Unique dead end identifier.
            title: Display title.
            description: What was attempted and why it failed.
            status: Dead end status.
            dry_run: If ``True``, validate without persisting.
            related_predictions: IDs of related predictions.
            related_claims: IDs of related claims.
            references: External reference strings.
            source: Provenance reference.

        Returns:
            ClientResult[DeadEnd]: The registered dead end entity.
        """
        return cast(
            ClientResult[DeadEnd],
            self.register(
                "dead_end",
                dry_run=dry_run,
                **_without_none(
                    id=id,
                    title=title,
                    description=description,
                    status=status,
                    related_predictions=list(related_predictions)
                    if related_predictions is not None else None,
                    related_claims=list(related_claims)
                    if related_claims is not None else None,
                    references=list(references) if references is not None else None,
                    source=source,
                ),
            ),
        )

    def register_parameter(
        self,
        id: str,
        name: str,
        value: object,
        *,
        dry_run: bool = False,
        unit: str | None = None,
        uncertainty: object | None = None,
        source: str | None = None,
        notes: str | None = None,
    ) -> ClientResult[Parameter]:
        """Register a parameter with typed keyword arguments.

        Args:
            id: Unique parameter identifier.
            name: Display name.
            value: The parameter value.
            dry_run: If ``True``, validate without persisting.
            unit: Unit of measurement.
            uncertainty: Uncertainty value or range.
            source: Provenance reference.
            notes: Free-form notes.

        Returns:
            ClientResult[Parameter]: The registered parameter entity.
        """
        return cast(
            ClientResult[Parameter],
            self.register(
                "parameter",
                dry_run=dry_run,
                **_without_none(
                    id=id,
                    name=name,
                    value=value,
                    unit=unit,
                    uncertainty=uncertainty,
                    source=source,
                    notes=notes,
                ),
            ),
        )

    def register_independence_group(
        self,
        id: str,
        label: str,
        *,
        dry_run: bool = False,
        claim_lineage: Iterable[str] | None = None,
        assumption_lineage: Iterable[str] | None = None,
        measurement_regime: MeasurementRegime | str | None = None,
        notes: str | None = None,
    ) -> ClientResult[IndependenceGroup]:
        """Register an independence group with typed keyword arguments.

        Args:
            id: Unique independence group identifier.
            label: Display label.
            dry_run: If ``True``, validate without persisting.
            claim_lineage: IDs of claims in the group's derivation lineage.
            assumption_lineage: IDs of assumptions in the group's derivation lineage.
            measurement_regime: Measurement regime classification.
            notes: Free-form notes.

        Returns:
            ClientResult[IndependenceGroup]: The registered group entity.
        """
        return cast(
            ClientResult[IndependenceGroup],
            self.register(
                "independence_group",
                dry_run=dry_run,
                **_without_none(
                    id=id,
                    label=label,
                    claim_lineage=list(claim_lineage)
                    if claim_lineage is not None else None,
                    assumption_lineage=list(assumption_lineage)
                    if assumption_lineage is not None else None,
                    measurement_regime=measurement_regime,
                    notes=notes,
                ),
            ),
        )

    def register_pairwise_separation(
        self,
        id: str,
        group_a: str,
        group_b: str,
        basis: str,
        *,
        dry_run: bool = False,
    ) -> ClientResult[PairwiseSeparation]:
        """Register a pairwise separation record.

        Args:
            id: Unique separation record identifier.
            group_a: ID of the first independence group.
            group_b: ID of the second independence group.
            basis: Justification for the separation.
            dry_run: If ``True``, validate without persisting.

        Returns:
            ClientResult[PairwiseSeparation]: The registered separation.
        """
        return cast(
            ClientResult[PairwiseSeparation],
            self.register(
                "pairwise_separation",
                dry_run=dry_run,
                id=id,
                group_a=group_a,
                group_b=group_b,
                basis=basis,
            ),
        )

    def get_claim(self, identifier: str) -> ClientResult[Claim]:
        """Retrieve a claim by ID."""
        return cast(ClientResult[Claim], self.get("claim", identifier))

    def get_assumption(self, identifier: str) -> ClientResult[Assumption]:
        """Retrieve an assumption by ID."""
        return cast(ClientResult[Assumption], self.get("assumption", identifier))

    def get_prediction(self, identifier: str) -> ClientResult[Prediction]:
        """Retrieve a prediction by ID."""
        return cast(ClientResult[Prediction], self.get("prediction", identifier))

    def get_analysis(self, identifier: str) -> ClientResult[Analysis]:
        """Retrieve an analysis by ID."""
        return cast(ClientResult[Analysis], self.get("analysis", identifier))

    def get_theory(self, identifier: str) -> ClientResult[Theory]:
        """Retrieve a theory by ID."""
        return cast(ClientResult[Theory], self.get("theory", identifier))

    def get_discovery(self, identifier: str) -> ClientResult[Discovery]:
        """Retrieve a discovery by ID."""
        return cast(ClientResult[Discovery], self.get("discovery", identifier))

    def get_dead_end(self, identifier: str) -> ClientResult[DeadEnd]:
        """Retrieve a dead end by ID."""
        return cast(ClientResult[DeadEnd], self.get("dead_end", identifier))

    def get_parameter(self, identifier: str) -> ClientResult[Parameter]:
        """Retrieve a parameter by ID."""
        return cast(ClientResult[Parameter], self.get("parameter", identifier))

    def get_independence_group(self, identifier: str) -> ClientResult[IndependenceGroup]:
        """Retrieve an independence group by ID."""
        return cast(ClientResult[IndependenceGroup], self.get("independence_group", identifier))

    def get_pairwise_separation(self, identifier: str) -> ClientResult[PairwiseSeparation]:
        """Retrieve a pairwise separation by ID."""
        return cast(ClientResult[PairwiseSeparation], self.get("pairwise_separation", identifier))

    def list_claims(self, **filters: object) -> ClientResult[list[Claim]]:
        """List all claims, optionally filtered."""
        return cast(ClientResult[list[Claim]], self.list("claim", **filters))

    def list_assumptions(self, **filters: object) -> ClientResult[list[Assumption]]:
        """List all assumptions, optionally filtered."""
        return cast(ClientResult[list[Assumption]], self.list("assumption", **filters))

    def list_predictions(self, **filters: object) -> ClientResult[list[Prediction]]:
        """List all predictions, optionally filtered."""
        return cast(ClientResult[list[Prediction]], self.list("prediction", **filters))

    def list_analyses(self, **filters: object) -> ClientResult[list[Analysis]]:
        """List all analyses, optionally filtered."""
        return cast(ClientResult[list[Analysis]], self.list("analysis", **filters))

    def list_theories(self, **filters: object) -> ClientResult[list[Theory]]:
        """List all theories, optionally filtered."""
        return cast(ClientResult[list[Theory]], self.list("theory", **filters))

    def list_discoveries(self, **filters: object) -> ClientResult[list[Discovery]]:
        """List all discoveries, optionally filtered."""
        return cast(ClientResult[list[Discovery]], self.list("discovery", **filters))

    def list_dead_ends(self, **filters: object) -> ClientResult[list[DeadEnd]]:
        """List all dead ends, optionally filtered."""
        return cast(ClientResult[list[DeadEnd]], self.list("dead_end", **filters))

    def list_parameters(self, **filters: object) -> ClientResult[list[Parameter]]:
        """List all parameters, optionally filtered."""
        return cast(ClientResult[list[Parameter]], self.list("parameter", **filters))

    def list_independence_groups(self, **filters: object) -> ClientResult[list[IndependenceGroup]]:
        """List all independence groups, optionally filtered."""
        return cast(ClientResult[list[IndependenceGroup]], self.list("independence_group", **filters))

    def list_pairwise_separations(self, **filters: object) -> ClientResult[list[PairwiseSeparation]]:
        """List all pairwise separations, optionally filtered."""
        return cast(ClientResult[list[PairwiseSeparation]], self.list("pairwise_separation", **filters))

    def transition_claim(
        self,
        identifier: str,
        new_status: ClaimStatus | str,
        *,
        dry_run: bool = False,
    ) -> ClientResult[Claim]:
        """Transition a claim to a new status."""
        return cast(
            ClientResult[Claim],
            self.transition("claim", identifier, new_status, dry_run=dry_run),
        )

    def transition_prediction(
        self,
        identifier: str,
        new_status: PredictionStatus | str,
        *,
        dry_run: bool = False,
    ) -> ClientResult[Prediction]:
        """Transition a prediction to a new status."""
        return cast(
            ClientResult[Prediction],
            self.transition("prediction", identifier, new_status, dry_run=dry_run),
        )

    def transition_theory(
        self,
        identifier: str,
        new_status: TheoryStatus | str,
        *,
        dry_run: bool = False,
    ) -> ClientResult[Theory]:
        """Transition a theory to a new status."""
        return cast(
            ClientResult[Theory],
            self.transition("theory", identifier, new_status, dry_run=dry_run),
        )

    def transition_discovery(
        self,
        identifier: str,
        new_status: DiscoveryStatus | str,
        *,
        dry_run: bool = False,
    ) -> ClientResult[Discovery]:
        """Transition a discovery to a new status."""
        return cast(
            ClientResult[Discovery],
            self.transition("discovery", identifier, new_status, dry_run=dry_run),
        )

    def transition_dead_end(
        self,
        identifier: str,
        new_status: DeadEndStatus | str,
        *,
        dry_run: bool = False,
    ) -> ClientResult[DeadEnd]:
        """Transition a dead end to a new status."""
        return cast(
            ClientResult[DeadEnd],
            self.transition("dead_end", identifier, new_status, dry_run=dry_run),
        )

    def _invoke_gateway(self, func, *args, **kwargs) -> GatewayResult:
        """Call a gateway method, wrapping unexpected errors in DeSitterClientError."""
        try:
            return func(*args, **kwargs)
        except DeSitterClientError:
            raise
        except Exception as exc:
            raise DeSitterClientError("error", str(exc)) from exc

    def _handle_resource_result(
        self,
        resource: str,
        result: GatewayResult,
    ) -> ClientResult[Any]:
        """Convert a gateway result into a typed ClientResult with a deserialized entity.

        Raises DeSitterClientError if the result status is not success.
        """
        if result.status not in {"ok", "dry_run"}:
            raise DeSitterClientError(result.status, result.message, result.findings)

        canonical = self._canonical_resource(resource)
        decoded = None
        if result.data is not None:
            resource_payload = result.data.get("resource")
            if isinstance(resource_payload, dict):
                decoded = deserialize_entity(canonical, resource_payload)

        return ClientResult(
            status=result.status,
            changed=result.changed,
            message=result.message,
            findings=result.findings,
            transaction_id=result.transaction_id,
            data=decoded,
        )

    def _handle_resource_list_result(
        self,
        resource: str,
        result: GatewayResult,
    ) -> ClientResult[list[Any]]:
        """Convert a gateway list result into a typed ClientResult with deserialized entities.

        Raises DeSitterClientError if the result status is not success.
        """
        if result.status not in {"ok", "dry_run"}:
            raise DeSitterClientError(result.status, result.message, result.findings)

        canonical = self._canonical_resource(resource)
        items: list[Any] = []
        if result.data is not None:
            raw_items = result.data.get("items", [])
            items = [deserialize_entity(canonical, item) for item in raw_items]

        return ClientResult(
            status=result.status,
            changed=result.changed,
            message=result.message,
            findings=result.findings,
            transaction_id=result.transaction_id,
            data=items,
        )

    def _handle_query_result(self, result: GatewayResult) -> ClientResult[Any]:
        """Convert a gateway query result into a typed ClientResult.

        Raises DeSitterClientError if the result status is not success.
        """
        if result.status not in {"ok", "dry_run"}:
            raise DeSitterClientError(result.status, result.message, result.findings)

        decoded: Any = None
        if result.data is not None:
            decoded = result.data.get("result", result.data)

        return ClientResult(
            status=result.status,
            changed=result.changed,
            message=result.message,
            findings=result.findings,
            transaction_id=result.transaction_id,
            data=decoded,
        )

    def _canonical_resource(self, resource: str) -> str:
        """Resolve a resource alias to its canonical key, falling back to the input."""
        try:
            canonical = self._gateway.resolve_resource(resource)
            return canonical if isinstance(canonical, str) else resource
        except KeyError:
            return resource


def connect(path: str | Path = ".") -> DeSitterClient:
    """Build a client from a workspace path containing ``desitter.toml``.

    This is the primary convenience entry point for creating a client.
    Loads configuration and builds the full dependency graph automatically.

    Args:
        path: Filesystem path to the project workspace root. Defaults to current directory.

    Returns:
        DeSitterClient: A fully wired client ready for use.
    """
    workspace = Path(path)
    context = build_context(workspace, load_config(workspace))
    return DeSitterClient(context)


def _without_none(**payload: object) -> dict[str, object]:
    """Filter out ``None`` values from keyword arguments."""
    return {
        key: value
        for key, value in payload.items()
        if value is not None
    }


__all__ = [
    "ClientResult",
    "DeSitterClient",
    "DeSitterClientError",
    "connect",
]