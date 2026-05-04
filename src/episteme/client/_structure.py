"""Client helper implementations for structural support resources."""
from __future__ import annotations

from typing import Iterable

from ._types import ClientResult
from ..epistemic.model import IndependenceGroup, PairwiseSeparation, Parameter
from ..epistemic.types import MeasurementRegime


class _EpistemeClientStructureHelpers:
    """Typed helpers for parameters and evidence-structure resources."""

    # ── Parameter ─────────────────────────────────────────────────

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
        tags: Iterable[str] | None = None,
    ) -> ClientResult[Parameter]:
        return self.register(
            "parameter",
            dry_run=dry_run,
            id=id,
            name=name,
            value=value,
            unit=unit,
            uncertainty=uncertainty,
            source=source,
            notes=notes,
            tags=list(tags) if tags is not None else None,
        )

    def get_parameter(self, identifier: str) -> ClientResult[Parameter]:
        return self.get("parameter", identifier)

    def list_parameters(self, **filters: object) -> ClientResult[list[Parameter]]:
        return self.list("parameter", **filters)

    def set_parameter(
        self, identifier: str, *, dry_run: bool = False, **payload: object
    ) -> ClientResult[Parameter]:
        return self.set("parameter", identifier, dry_run=dry_run, **payload)

    # ── IndependenceGroup ─────────────────────────────────────────

    def register_independence_group(
        self,
        id: str,
        label: str,
        *,
        dry_run: bool = False,
        hypothesis_lineage: Iterable[str] | None = None,
        assumption_lineage: Iterable[str] | None = None,
        measurement_regime: MeasurementRegime | str | None = None,
        notes: str | None = None,
    ) -> ClientResult[IndependenceGroup]:
        regime = (
            measurement_regime
            if isinstance(measurement_regime, str) or measurement_regime is None
            else measurement_regime.value
        )
        return self.register(
            "independence_group",
            dry_run=dry_run,
            id=id,
            label=label,
            hypothesis_lineage=list(hypothesis_lineage) if hypothesis_lineage is not None else None,
            assumption_lineage=list(assumption_lineage) if assumption_lineage is not None else None,
            measurement_regime=regime,
            notes=notes,
        )

    def get_independence_group(self, identifier: str) -> ClientResult[IndependenceGroup]:
        return self.get("independence_group", identifier)

    def list_independence_groups(self, **filters: object) -> ClientResult[list[IndependenceGroup]]:
        return self.list("independence_group", **filters)

    def set_independence_group(
        self, identifier: str, *, dry_run: bool = False, **payload: object
    ) -> ClientResult[IndependenceGroup]:
        return self.set("independence_group", identifier, dry_run=dry_run, **payload)

    # ── PairwiseSeparation ────────────────────────────────────────

    def register_pairwise_separation(
        self,
        id: str,
        group_a: str,
        group_b: str,
        basis: str,
        *,
        dry_run: bool = False,
    ) -> ClientResult[PairwiseSeparation]:
        return self.register(
            "pairwise_separation",
            dry_run=dry_run,
            id=id,
            group_a=group_a,
            group_b=group_b,
            basis=basis,
        )

    def get_pairwise_separation(self, identifier: str) -> ClientResult[PairwiseSeparation]:
        return self.get("pairwise_separation", identifier)

    def list_pairwise_separations(self, **filters: object) -> ClientResult[list[PairwiseSeparation]]:
        return self.list("pairwise_separation", **filters)


__all__ = ["_EpistemeClientStructureHelpers"]

