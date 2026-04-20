"""Client helper declarations for structural support resources."""
from __future__ import annotations

from typing import Iterable

from ._types import ClientResult
from ..epistemic.model import IndependenceGroup, PairwiseSeparation, Parameter
from ..epistemic.types import MeasurementRegime


class _EpistemeClientStructureHelpers:
    """Typed helpers for parameters and evidence-structure resources."""

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
        """Register a named parameter in the epistemic graph.

        Parameters capture physical or statistical quantities whose values
        inform or constrain predictions and analyses.

        Args:
            id: Unique identifier for the parameter.
            name: Human-readable parameter name (e.g. ``"Hubble constant"``).
            value: Numeric or string value of the parameter.
            dry_run: Simulate without committing.
            unit: Unit string (e.g. ``"km/s/Mpc"``).
            uncertainty: Uncertainty or error bound on the value.
            source: Citation or reference.
            notes: Free-text supplementary notes.

        Returns:
            ``ClientResult[Parameter]`` with ``status="ok"`` and ``data``
            holding the registered entity on success.

        Raises:
            NotImplementedError: This stub is not yet implemented.
        """
        raise NotImplementedError

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
        """Register an independence group in the epistemic graph.

        Independence groups collect evidence streams that are statistically
        independent of one another, which is used to evaluate whether the
        project's predictions are independently supported.

        Args:
            id: Unique identifier for the group.
            label: Human-readable descriptive label.
            dry_run: Simulate without committing.
            claim_lineage: IDs of claims that define the conceptual scope of
                this independence group.
            assumption_lineage: IDs of assumptions shared by members of this
                group.
            measurement_regime: The measurement approach used by the group
                (``MeasurementRegime`` enum or string key).
            notes: Free-text supplementary notes.

        Returns:
            ``ClientResult[IndependenceGroup]`` with ``status="ok"`` and
            ``data`` holding the registered entity on success.

        Raises:
            NotImplementedError: This stub is not yet implemented.
        """
        raise NotImplementedError

    def register_pairwise_separation(
        self,
        id: str,
        group_a: str,
        group_b: str,
        basis: str,
        *,
        dry_run: bool = False,
    ) -> ClientResult[PairwiseSeparation]:
        """Register a pairwise separation between two independence groups.

        A pairwise separation documents the specific basis on which two
        independence groups are claimed to be statistically independent.

        Args:
            id: Unique identifier for the pairwise separation.
            group_a: ID of the first independence group.
            group_b: ID of the second independence group.
            basis: Free-text description of why the two groups are independent.
            dry_run: Simulate without committing.

        Returns:
            ``ClientResult[PairwiseSeparation]`` with ``status="ok"`` and
            ``data`` holding the registered entity on success.

        Raises:
            NotImplementedError: This stub is not yet implemented.
        """
        raise NotImplementedError

    def get_parameter(self, identifier: str) -> ClientResult[Parameter]:
        """Retrieve a parameter by its unique identifier.

        Args:
            identifier: The unique string ID of the parameter to look up.

        Returns:
            ``ClientResult[Parameter]`` with ``status="ok"`` and ``data``
            set to the entity when found, or ``status="error"`` if not found.

        Raises:
            NotImplementedError: This stub is not yet implemented.
        """
        raise NotImplementedError

    def get_independence_group(self, identifier: str) -> ClientResult[IndependenceGroup]:
        """Retrieve an independence group by its unique identifier.

        Args:
            identifier: The unique string ID of the independence group to look
                up.

        Returns:
            ``ClientResult[IndependenceGroup]`` with ``status="ok"`` and
            ``data`` set to the entity when found, or ``status="error"`` if
            not found.

        Raises:
            NotImplementedError: This stub is not yet implemented.
        """
        raise NotImplementedError

    def get_pairwise_separation(self, identifier: str) -> ClientResult[PairwiseSeparation]:
        """Retrieve a pairwise separation by its unique identifier.

        Args:
            identifier: The unique string ID of the pairwise separation to
                look up.

        Returns:
            ``ClientResult[PairwiseSeparation]`` with ``status="ok"`` and
            ``data`` set to the entity when found, or ``status="error"`` if
            not found.

        Raises:
            NotImplementedError: This stub is not yet implemented.
        """
        raise NotImplementedError

    def list_parameters(self, **filters: object) -> ClientResult[list[Parameter]]:
        """Return all parameters, applying any keyword attribute filters.

        Args:
            **filters: Attribute-value pairs to filter on (e.g.
                ``unit="km/s/Mpc"`` to return only parameters with that unit).

        Returns:
            ``ClientResult[list[Parameter]]`` with ``data`` holding the
            (possibly empty) list of matching parameters.

        Raises:
            NotImplementedError: This stub is not yet implemented.
        """
        raise NotImplementedError

    def list_independence_groups(self, **filters: object) -> ClientResult[list[IndependenceGroup]]:
        """Return all independence groups, applying any keyword attribute filters.

        Args:
            **filters: Attribute-value pairs to filter on.

        Returns:
            ``ClientResult[list[IndependenceGroup]]`` with ``data`` holding
            the (possibly empty) list of matching groups.

        Raises:
            NotImplementedError: This stub is not yet implemented.
        """
        raise NotImplementedError

    def list_pairwise_separations(self, **filters: object) -> ClientResult[list[PairwiseSeparation]]:
        """Return all pairwise separations, applying any keyword attribute filters.

        Args:
            **filters: Attribute-value pairs to filter on.

        Returns:
            ``ClientResult[list[PairwiseSeparation]]`` with ``data`` holding
            the (possibly empty) list of matching separations.

        Raises:
            NotImplementedError: This stub is not yet implemented.
        """
        raise NotImplementedError


__all__ = ["_EpistemeClientStructureHelpers"]
