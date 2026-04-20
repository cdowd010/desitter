"""Client helper declarations for core hypothesis resources."""
from __future__ import annotations

from datetime import date
from typing import Iterable, Mapping

from ._types import ClientResult
from ..epistemic.model import Analysis, Assumption, Claim, Prediction
from ..epistemic.types import (
    AssumptionType,
    ClaimCategory,
    ClaimStatus,
    ClaimType,
    ConfidenceTier,
    EvidenceKind,
    MeasurementRegime,
    PredictionStatus,
)


class _EpistemeClientHypothesisHelpers:
    """Typed helpers for claims, assumptions, predictions, and analyses."""

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
        """Register a claim in the epistemic graph.

        Args:
            id: Unique identifier for the claim (e.g. ``"c-mass-energy"``).
            statement: Human-readable statement of the claim.
            type: Epistemological type (``ClaimType`` enum or its string key).
            scope: Domain scope string identifying the area of the claim.
            falsifiability: Description of how this claim could be falsified.
            dry_run: Simulate the mutation without committing. Defaults to
                ``False``.
            status: Initial lifecycle status. Falls back to the graph default
                when ``None``.
            category: Optional category tag (``ClaimCategory`` enum or string
                key).
            assumptions: IDs of assumptions that underpin this claim.
            depends_on: IDs of claims this claim logically depends on.
            analyses: IDs of analyses that supply evidence for this claim.
            parameter_constraints: Mapping of parameter names to constraint
                descriptions.
            source: Citation or reference supporting the claim.

        Returns:
            ``ClientResult[Claim]`` with ``status="ok"`` and ``data`` holding
            the registered entity on success; ``status="BLOCKED"`` if a
            domain invariant prevents the write.

        Raises:
            NotImplementedError: This stub is not yet implemented.
        """
        raise NotImplementedError

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
        """Register an assumption in the epistemic graph.

        Args:
            id: Unique identifier for the assumption.
            statement: Human-readable statement of the assumption.
            type: Epistemological type (``AssumptionType`` enum or string key).
            scope: Domain scope string situating the assumption in context.
            dry_run: Simulate the mutation without committing.
            depends_on: IDs of other assumptions this one rests on.
            falsifiable_consequence: A testable prediction that would refute
                this assumption if it failed.
            source: Citation or reference.
            notes: Free-text supplementary notes.

        Returns:
            ``ClientResult[Assumption]`` with ``status="ok"`` and ``data``
            holding the registered entity on success.

        Raises:
            NotImplementedError: This stub is not yet implemented.
        """
        raise NotImplementedError

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
        """Register a prediction in the epistemic graph.

        Args:
            id: Unique identifier for the prediction.
            observable: The quantity or phenomenon the prediction concerns.
            tier: Confidence tier (``ConfidenceTier`` enum or string key).
            status: Initial lifecycle status (``PredictionStatus`` enum or
                string key).
            evidence_kind: Kind of evidence used to evaluate the prediction
                (``EvidenceKind`` enum or string key).
            measurement_regime: Measurement approach (``MeasurementRegime``
                enum or string key).
            predicted: The predicted value or distribution.
            dry_run: Simulate without committing.
            specification: Detailed numerical specification of the prediction.
            derivation: Theoretical derivation of the predicted value.
            claim_ids: IDs of claims this prediction flows from.
            tests_assumptions: IDs of assumptions this prediction tests.
            analysis: ID of the analysis responsible for evaluation.
            independence_group: ID of the independence group this prediction
                belongs to.
            correlation_tags: Tags marking predictions that share correlated
                data.
            observed: The observed value (``None`` while pending).
            observed_bound: Upper or lower bound on the observed value.
            free_params: Number of free parameters used in deriving the
                prediction.
            conditional_on: IDs of predictions this one is conditional on.
            falsifier: Description of what would falsify this prediction.
            benchmark_source: Citation for the benchmark value.
            source: General citation or reference.
            notes: Free-text supplementary notes.

        Returns:
            ``ClientResult[Prediction]`` with ``status="ok"`` and ``data``
            holding the registered entity on success.

        Raises:
            NotImplementedError: This stub is not yet implemented.
        """
        raise NotImplementedError

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
        """Register an analysis node in the epistemic graph.

        An analysis represents a runnable computation or procedure that
        produces evidence for one or more predictions or claims.

        Args:
            id: Unique identifier for the analysis.
            dry_run: Simulate without committing.
            command: Shell command or script invocation used to run the
                analysis.
            path: Path to the analysis script or notebook.
            uses_parameters: IDs of parameters consumed by this analysis.
            notes: Free-text supplementary notes.
            last_result: Most recent output value from a previous run.
            last_result_sha: Git SHA of the commit that produced
                ``last_result``.
            last_result_date: Date of the most recent run.

        Returns:
            ``ClientResult[Analysis]`` with ``status="ok"`` and ``data``
            holding the registered entity on success.

        Raises:
            NotImplementedError: This stub is not yet implemented.
        """
        raise NotImplementedError

    def get_claim(self, identifier: str) -> ClientResult[Claim]:
        """Retrieve a claim by its unique identifier.

        Args:
            identifier: The unique string ID of the claim to look up.

        Returns:
            ``ClientResult[Claim]`` with ``status="ok"`` and ``data`` set to
            the entity when found, or ``status="error"`` if no claim with
            that ID exists.

        Raises:
            NotImplementedError: This stub is not yet implemented.
        """
        raise NotImplementedError

    def get_assumption(self, identifier: str) -> ClientResult[Assumption]:
        """Retrieve an assumption by its unique identifier.

        Args:
            identifier: The unique string ID of the assumption to look up.

        Returns:
            ``ClientResult[Assumption]`` with ``status="ok"`` and ``data``
            set to the entity when found, or ``status="error"`` if not found.

        Raises:
            NotImplementedError: This stub is not yet implemented.
        """
        raise NotImplementedError

    def get_prediction(self, identifier: str) -> ClientResult[Prediction]:
        """Retrieve a prediction by its unique identifier.

        Args:
            identifier: The unique string ID of the prediction to look up.

        Returns:
            ``ClientResult[Prediction]`` with ``status="ok"`` and ``data``
            set to the entity when found, or ``status="error"`` if not found.

        Raises:
            NotImplementedError: This stub is not yet implemented.
        """
        raise NotImplementedError

    def get_analysis(self, identifier: str) -> ClientResult[Analysis]:
        """Retrieve an analysis node by its unique identifier.

        Args:
            identifier: The unique string ID of the analysis to look up.

        Returns:
            ``ClientResult[Analysis]`` with ``status="ok"`` and ``data``
            set to the entity when found, or ``status="error"`` if not found.

        Raises:
            NotImplementedError: This stub is not yet implemented.
        """
        raise NotImplementedError

    def list_claims(self, **filters: object) -> ClientResult[list[Claim]]:
        """Return all claims, applying any keyword attribute filters.

        Keyword filters are matched against entity attribute values. A claim
        is included only when every supplied filter matches.

        Args:
            **filters: Attribute-value pairs to filter on (e.g.
                ``status="active"`` to return only active claims).

        Returns:
            ``ClientResult[list[Claim]]`` with ``data`` holding the
            (possibly empty) list of matching claims.

        Raises:
            NotImplementedError: This stub is not yet implemented.
        """
        raise NotImplementedError

    def list_assumptions(self, **filters: object) -> ClientResult[list[Assumption]]:
        """Return all assumptions, applying any keyword attribute filters.

        Args:
            **filters: Attribute-value pairs to filter on (e.g.
                ``type="domain"`` to return only domain-type assumptions).

        Returns:
            ``ClientResult[list[Assumption]]`` with ``data`` holding the
            (possibly empty) list of matching assumptions.

        Raises:
            NotImplementedError: This stub is not yet implemented.
        """
        raise NotImplementedError

    def list_predictions(self, **filters: object) -> ClientResult[list[Prediction]]:
        """Return all predictions, applying any keyword attribute filters.

        Args:
            **filters: Attribute-value pairs to filter on (e.g.
                ``status="pending"`` to return only pending predictions,
                ``tier="A"`` to return Tier-A predictions).

        Returns:
            ``ClientResult[list[Prediction]]`` with ``data`` holding the
            (possibly empty) list of matching predictions.

        Raises:
            NotImplementedError: This stub is not yet implemented.
        """
        raise NotImplementedError

    def list_analyses(self, **filters: object) -> ClientResult[list[Analysis]]:
        """Return all analysis nodes, applying any keyword attribute filters.

        Args:
            **filters: Attribute-value pairs to filter on.

        Returns:
            ``ClientResult[list[Analysis]]`` with ``data`` holding the
            (possibly empty) list of matching analysis nodes.

        Raises:
            NotImplementedError: This stub is not yet implemented.
        """
        raise NotImplementedError

    def transition_claim(
        self,
        identifier: str,
        new_status: ClaimStatus | str,
        *,
        dry_run: bool = False,
    ) -> ClientResult[Claim]:
        """Advance or retract a claim's lifecycle status.

        Args:
            identifier: The unique string ID of the claim to transition.
            new_status: Target lifecycle status (``ClaimStatus`` enum value
                or its string key).
            dry_run: Simulate the transition without committing.

        Returns:
            ``ClientResult[Claim]`` with ``status="ok"`` and ``data`` holding
            the updated entity, or ``status="BLOCKED"`` if the transition
            violates a domain invariant.

        Raises:
            NotImplementedError: This stub is not yet implemented.
        """
        raise NotImplementedError

    def transition_prediction(
        self,
        identifier: str,
        new_status: PredictionStatus | str,
        *,
        dry_run: bool = False,
    ) -> ClientResult[Prediction]:
        """Advance or retract a prediction's lifecycle status.

        Args:
            identifier: The unique string ID of the prediction to transition.
            new_status: Target lifecycle status (``PredictionStatus`` enum
                value or its string key).
            dry_run: Simulate the transition without committing.

        Returns:
            ``ClientResult[Prediction]`` with ``status="ok"`` and ``data``
            holding the updated entity, or ``status="BLOCKED"`` if the
            transition violates a domain invariant.

        Raises:
            NotImplementedError: This stub is not yet implemented.
        """
        raise NotImplementedError


__all__ = ["_EpistemeClientHypothesisHelpers"]
