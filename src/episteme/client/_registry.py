"""Client helper declarations for narrative and registry resources."""
from __future__ import annotations

from datetime import date
from typing import Iterable

from ._types import ClientResult
from ..epistemic.model import DeadEnd, Discovery, Theory
from ..epistemic.types import DeadEndStatus, DiscoveryStatus, TheoryStatus


class _EpistemeClientRegistryHelpers:
    """Typed helpers for theories, discoveries, and dead ends."""

    def register_theory(
        self,
        id: str,
        title: str,
        status: TheoryStatus | str,
        *,
        dry_run: bool = False,
        summary: str | None = None,
        related_predictions: Iterable[str] | None = None,
        source: str | None = None,
    ) -> ClientResult[Theory]:
        """Register a theory in the epistemic graph.

        A theory is a high-level narrative construct that groups related claims
        and predictions into a coherent explanatory framework. Claims declare
        which theories motivate them via ``Claim.theories``; the theory's
        ``motivates_claims`` backlink is auto-maintained.

        Args:
            id: Unique identifier for the theory.
            title: Short descriptive title.
            status: Initial lifecycle status (``TheoryStatus`` enum or string
                key).
            dry_run: Simulate without committing.
            summary: Extended free-text summary of the theory.
            related_predictions: IDs of predictions associated with this
                theory.
            source: Citation or reference.

        Returns:
            ``ClientResult[Theory]`` with ``status="ok"`` and ``data`` holding
            the registered entity on success.

        Raises:
            NotImplementedError: This stub is not yet implemented.
        """
        raise NotImplementedError

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
        """Register a discovery in the epistemic graph.

        A discovery records a confirmed empirical or theoretical result that
        advances the project's understanding.

        Args:
            id: Unique identifier for the discovery.
            title: Short descriptive title.
            date: Date the discovery was made (``date`` object or ISO string).
            summary: Human-readable summary of what was discovered.
            impact: Description of the scientific impact.
            status: Initial lifecycle status (``DiscoveryStatus`` enum or
                string key).
            dry_run: Simulate without committing.
            related_claims: IDs of claims that this discovery supports or
                refines.
            related_predictions: IDs of predictions that this discovery
                confirms or falsifies.
            references: Citations or URLs documenting the discovery.
            source: General citation or reference.

        Returns:
            ``ClientResult[Discovery]`` with ``status="ok"`` and ``data``
            holding the registered entity on success.

        Raises:
            NotImplementedError: This stub is not yet implemented.
        """
        raise NotImplementedError

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
        """Register a dead end in the epistemic graph.

        A dead end documents an approach or hypothesis that was pursued but
        ultimately abandoned, preserving the negative knowledge.

        Args:
            id: Unique identifier for the dead end.
            title: Short descriptive title.
            description: Detailed description of the approach and why it
                failed.
            status: Initial lifecycle status (``DeadEndStatus`` enum or
                string key).
            dry_run: Simulate without committing.
            related_predictions: IDs of predictions that were falsified or
                superseded by this dead end.
            related_claims: IDs of claims this dead end is connected to.
            references: Citations or URLs documenting the failed approach.
            source: General citation or reference.

        Returns:
            ``ClientResult[DeadEnd]`` with ``status="ok"`` and ``data``
            holding the registered entity on success.

        Raises:
            NotImplementedError: This stub is not yet implemented.
        """
        raise NotImplementedError

    def get_theory(self, identifier: str) -> ClientResult[Theory]:
        """Retrieve a theory by its unique identifier.

        Args:
            identifier: The unique string ID of the theory to look up.

        Returns:
            ``ClientResult[Theory]`` with ``status="ok"`` and ``data`` set to
            the entity when found, or ``status="error"`` if not found.

        Raises:
            NotImplementedError: This stub is not yet implemented.
        """
        raise NotImplementedError

    def get_discovery(self, identifier: str) -> ClientResult[Discovery]:
        """Retrieve a discovery by its unique identifier.

        Args:
            identifier: The unique string ID of the discovery to look up.

        Returns:
            ``ClientResult[Discovery]`` with ``status="ok"`` and ``data``
            set to the entity when found, or ``status="error"`` if not found.

        Raises:
            NotImplementedError: This stub is not yet implemented.
        """
        raise NotImplementedError

    def get_dead_end(self, identifier: str) -> ClientResult[DeadEnd]:
        """Retrieve a dead end by its unique identifier.

        Args:
            identifier: The unique string ID of the dead end to look up.

        Returns:
            ``ClientResult[DeadEnd]`` with ``status="ok"`` and ``data`` set
            to the entity when found, or ``status="error"`` if not found.

        Raises:
            NotImplementedError: This stub is not yet implemented.
        """
        raise NotImplementedError

    def list_theories(self, **filters: object) -> ClientResult[list[Theory]]:
        """Return all theories, applying any keyword attribute filters.

        Args:
            **filters: Attribute-value pairs to filter on (e.g.
                ``status="active"`` to return only active theories).

        Returns:
            ``ClientResult[list[Theory]]`` with ``data`` holding the
            (possibly empty) list of matching theories.

        Raises:
            NotImplementedError: This stub is not yet implemented.
        """
        raise NotImplementedError

    def list_discoveries(self, **filters: object) -> ClientResult[list[Discovery]]:
        """Return all discoveries, applying any keyword attribute filters.

        Args:
            **filters: Attribute-value pairs to filter on (e.g.
                ``status="confirmed"`` to return only confirmed discoveries).

        Returns:
            ``ClientResult[list[Discovery]]`` with ``data`` holding the
            (possibly empty) list of matching discoveries.

        Raises:
            NotImplementedError: This stub is not yet implemented.
        """
        raise NotImplementedError

    def list_dead_ends(self, **filters: object) -> ClientResult[list[DeadEnd]]:
        """Return all dead ends, applying any keyword attribute filters.

        Args:
            **filters: Attribute-value pairs to filter on.

        Returns:
            ``ClientResult[list[DeadEnd]]`` with ``data`` holding the
            (possibly empty) list of matching dead ends.

        Raises:
            NotImplementedError: This stub is not yet implemented.
        """
        raise NotImplementedError

    def transition_theory(
        self,
        identifier: str,
        new_status: TheoryStatus | str,
        *,
        dry_run: bool = False,
    ) -> ClientResult[Theory]:
        """Advance or retract a theory's lifecycle status.

        Args:
            identifier: The unique string ID of the theory to transition.
            new_status: Target lifecycle status (``TheoryStatus`` enum value
                or its string key).
            dry_run: Simulate the transition without committing.

        Returns:
            ``ClientResult[Theory]`` with ``status="ok"`` and ``data`` holding
            the updated entity, or ``status="BLOCKED"`` if the transition
            violates a domain invariant.

        Raises:
            NotImplementedError: This stub is not yet implemented.
        """
        raise NotImplementedError

    def transition_discovery(
        self,
        identifier: str,
        new_status: DiscoveryStatus | str,
        *,
        dry_run: bool = False,
    ) -> ClientResult[Discovery]:
        """Advance or retract a discovery's lifecycle status.

        Args:
            identifier: The unique string ID of the discovery to transition.
            new_status: Target lifecycle status (``DiscoveryStatus`` enum
                value or its string key).
            dry_run: Simulate the transition without committing.

        Returns:
            ``ClientResult[Discovery]`` with ``status="ok"`` and ``data``
            holding the updated entity, or ``status="BLOCKED"`` if the
            transition violates a domain invariant.

        Raises:
            NotImplementedError: This stub is not yet implemented.
        """
        raise NotImplementedError

    def transition_dead_end(
        self,
        identifier: str,
        new_status: DeadEndStatus | str,
        *,
        dry_run: bool = False,
    ) -> ClientResult[DeadEnd]:
        """Advance or retract a dead end's lifecycle status.

        Args:
            identifier: The unique string ID of the dead end to transition.
            new_status: Target lifecycle status (``DeadEndStatus`` enum value
                or its string key).
            dry_run: Simulate the transition without committing.

        Returns:
            ``ClientResult[DeadEnd]`` with ``status="ok"`` and ``data``
            holding the updated entity, or ``status="BLOCKED"`` if the
            transition violates a domain invariant.

        Raises:
            NotImplementedError: This stub is not yet implemented.
        """
        raise NotImplementedError


__all__ = ["_EpistemeClientRegistryHelpers"]
