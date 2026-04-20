"""Concrete Episteme client and factory helpers.

This module assembles the final ``EpistemeClient`` class from its mixin
bases and exposes the ``connect`` factory used by callers.
"""
from __future__ import annotations

from ._core import _EpistemeClientCore
from ._resources import _EpistemeClientResourceHelpers
from ..epistemic.ports import EpistemicGraphPort, GraphRepository


class EpistemeClient(_EpistemeClientResourceHelpers, _EpistemeClientCore):
    """Python client that owns persistence and exposes typed helpers.

    ``EpistemeClient`` is the top-level object a researcher interacts
    with. It is constructed via ``connect()`` rather than directly.

    The class is assembled from three mixin bases:
    - ``_EpistemeClientCore``: lifecycle (save, context manager) and
      generic gateway operations (register, get, list, set, transition,
      query).
    - ``_EpistemeClientResourceHelpers`` (via ``_EpistemeClientResourceHelpers``):
      typed keyword-argument helpers for all ten entity types, delegating
      to the generic operations above.

    Usage::

        import episteme as ds

        with ds.connect() as client:
            result = client.register_claim(
                id="C-001",
                statement="...",
                type="foundational",
                scope="global",
                falsifiability="...",
            )
    """


def connect(
    *,
    repo: GraphRepository | None = None,
    graph: EpistemicGraphPort | None = None,
) -> EpistemeClient:
    """Build a ``EpistemeClient``, optionally backed by a repository.

    The typical researcher workflow is simply ``ds.connect()`` from a
    project workspace directory. The function loads the project config,
    derives paths, hydrates the graph, builds the gateway, and returns a
    ready-to-use client.

    Args:
        repo: Optional ``GraphRepository`` implementation to use for
            loading and saving. When provided, the graph is loaded from
            the repository before the client is returned. When ``None``,
            ``connect`` locates the repository automatically by searching
            for a ``episteme.toml`` in the current directory tree.
        graph: Optional pre-loaded ``EpistemicGraphPort`` instance. When
            provided, this graph is used directly and no repository load
            is performed. Useful for testing or in-memory workflows.
            Cannot be combined with ``repo``.

    Returns:
        EpistemeClient: A fully initialized client ready for use.

    Raises:
        NotImplementedError: Not yet implemented.
    """
    raise NotImplementedError


def _without_none(**payload: object) -> dict[str, object]:
    """Return a copy of *payload* with all ``None`` values removed.

    Used by typed helper methods to strip unset optional keyword
    arguments before forwarding to the generic ``register`` / ``set``
    operations, which pass payloads directly to the gateway.

    Args:
        **payload: Arbitrary keyword arguments to filter.

    Returns:
        dict[str, object]: A new dict containing only the entries from
            ``payload`` whose values are not ``None``.

    Raises:
        NotImplementedError: Not yet implemented.
    """
    raise NotImplementedError


__all__ = ["EpistemeClient", "_without_none", "connect"]
