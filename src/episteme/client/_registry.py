"""Client helper declarations for narrative and registry resources."""
from __future__ import annotations

from datetime import date
from typing import Iterable

from ._types import ClientResult
from ..epistemic.model import DeadEnd, Discovery, Objective
from ..epistemic.types import DeadEndStatus, DiscoveryStatus, ObjectiveStatus


class _EpistemeClientRegistryHelpers:
    """Typed helpers for objectives, discoveries, and dead ends."""

    # ── Objective ─────────────────────────────────────────────────

    def register_objective(
        self,
        id: str,
        title: str,
        kind: str,
        status: ObjectiveStatus | str,
        *,
        dry_run: bool = False,
        summary: str | None = None,
        success_criteria: str | None = None,
        related_predictions: Iterable[str] | None = None,
        related_dead_ends: Iterable[str] | None = None,
        related_discoveries: Iterable[str] | None = None,
        source: str | None = None,
    ) -> ClientResult[Objective]:
        status_str = status.value if isinstance(status, ObjectiveStatus) else status
        return self.register(
            "objective",
            dry_run=dry_run,
            id=id,
            title=title,
            kind=kind,
            status=status_str,
            summary=summary,
            success_criteria=success_criteria,
            related_predictions=list(related_predictions) if related_predictions is not None else None,
            related_dead_ends=list(related_dead_ends) if related_dead_ends is not None else None,
            related_discoveries=list(related_discoveries) if related_discoveries is not None else None,
            source=source,
        )

    def get_objective(self, identifier: str) -> ClientResult[Objective]:
        return self.get("objective", identifier)

    def list_objectives(self, **filters: object) -> ClientResult[list[Objective]]:
        return self.list("objective", **filters)

    def set_objective(
        self, identifier: str, *, dry_run: bool = False, **payload: object
    ) -> ClientResult[Objective]:
        return self.set("objective", identifier, dry_run=dry_run, **payload)

    def transition_objective(
        self,
        identifier: str,
        new_status: ObjectiveStatus | str,
        *,
        dry_run: bool = False,
    ) -> ClientResult[Objective]:
        return self.transition("objective", identifier, new_status, dry_run=dry_run)

    # ── Discovery ─────────────────────────────────────────────────

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
        related_hypotheses: Iterable[str] | None = None,
        related_predictions: Iterable[str] | None = None,
        references: Iterable[str] | None = None,
        source: str | None = None,
    ) -> ClientResult[Discovery]:
        status_str = status.value if isinstance(status, DiscoveryStatus) else status
        date_str = date.isoformat() if hasattr(date, "isoformat") else date
        return self.register(
            "discovery",
            dry_run=dry_run,
            id=id,
            title=title,
            date=date_str,
            summary=summary,
            impact=impact,
            status=status_str,
            related_hypotheses=list(related_hypotheses) if related_hypotheses is not None else None,
            related_predictions=list(related_predictions) if related_predictions is not None else None,
            references=list(references) if references is not None else None,
            source=source,
        )

    def get_discovery(self, identifier: str) -> ClientResult[Discovery]:
        return self.get("discovery", identifier)

    def list_discoveries(self, **filters: object) -> ClientResult[list[Discovery]]:
        return self.list("discovery", **filters)

    def set_discovery(
        self, identifier: str, *, dry_run: bool = False, **payload: object
    ) -> ClientResult[Discovery]:
        return self.set("discovery", identifier, dry_run=dry_run, **payload)

    def transition_discovery(
        self,
        identifier: str,
        new_status: DiscoveryStatus | str,
        *,
        dry_run: bool = False,
    ) -> ClientResult[Discovery]:
        return self.transition("discovery", identifier, new_status, dry_run=dry_run)

    # ── DeadEnd ───────────────────────────────────────────────────

    def register_dead_end(
        self,
        id: str,
        title: str,
        description: str,
        status: DeadEndStatus | str,
        *,
        dry_run: bool = False,
        related_predictions: Iterable[str] | None = None,
        related_hypotheses: Iterable[str] | None = None,
        references: Iterable[str] | None = None,
        source: str | None = None,
    ) -> ClientResult[DeadEnd]:
        status_str = status.value if isinstance(status, DeadEndStatus) else status
        return self.register(
            "dead_end",
            dry_run=dry_run,
            id=id,
            title=title,
            description=description,
            status=status_str,
            related_predictions=list(related_predictions) if related_predictions is not None else None,
            related_hypotheses=list(related_hypotheses) if related_hypotheses is not None else None,
            references=list(references) if references is not None else None,
            source=source,
        )

    def get_dead_end(self, identifier: str) -> ClientResult[DeadEnd]:
        return self.get("dead_end", identifier)

    def list_dead_ends(self, **filters: object) -> ClientResult[list[DeadEnd]]:
        return self.list("dead_end", **filters)

    def set_dead_end(
        self, identifier: str, *, dry_run: bool = False, **payload: object
    ) -> ClientResult[DeadEnd]:
        return self.set("dead_end", identifier, dry_run=dry_run, **payload)

    def transition_dead_end(
        self,
        identifier: str,
        new_status: DeadEndStatus | str,
        *,
        dry_run: bool = False,
    ) -> ClientResult[DeadEnd]:
        return self.transition("dead_end", identifier, new_status, dry_run=dry_run)


__all__ = ["_EpistemeClientRegistryHelpers"]
