"""Concrete Episteme client and factory helpers.

This module assembles the final ``EpistemeClient`` class from its mixin
bases and exposes the ``connect`` factory used by callers.
"""
from __future__ import annotations

from pathlib import Path

from ._core import _EpistemeClientCore
from ._resources import _EpistemeClientResourceHelpers
from ..adapters.json_repository import JsonRepository
from ..adapters.payload_validator import SchemaPayloadValidator
from ..adapters.transaction_log import JsonlTransactionLog
from ..config import build_context
from ..controlplane.factory import build_gateway
from ..epistemic.graph import EpistemicGraph
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
            result = client.register_hypothesis(
                id="C-001",
                statement="...",
                type="foundational",
                scope="global",
                refutation_criteria="...",
            )
    """


def connect(
    *,
    repo: GraphRepository | None = None,
    graph: EpistemicGraphPort | None = None,
    workspace: Path | str | None = None,
) -> EpistemeClient:
    """Build an ``EpistemeClient``, optionally backed by a repository.

    When called with no arguments from a project workspace, ``connect``
    searches for ``episteme.toml`` in the current directory to derive
    the graph file path, loads the graph, builds the gateway, and returns
    a ready-to-use client.

    Args:
        repo: Optional ``GraphRepository`` implementation. When provided,
            the graph is loaded from the repository on construction.
            Cannot be combined with ``graph``.
        graph: Optional pre-loaded ``EpistemicGraphPort`` instance.
            Used directly; no repository load is performed.
            Cannot be combined with ``repo``.
        workspace: Optional workspace root path. Defaults to the current
            working directory. Only used when neither ``repo`` nor
            ``graph`` is provided.

    Returns:
        EpistemeClient: A fully initialized client ready for use.
    """
    if repo is not None and graph is not None:
        raise ValueError("Cannot supply both 'repo' and 'graph' to connect()")

    payload_validator = SchemaPayloadValidator()

    if graph is not None:
        # Caller supplied a pre-loaded graph; no repository, no persistence.
        gw = build_gateway(graph, payload_validator=payload_validator)
        return EpistemeClient(gw)

    if repo is not None:
        # Caller supplied a repository; load the graph from it.
        loaded = repo.load()
        gw = build_gateway(loaded, payload_validator=payload_validator)
        return EpistemeClient(gw, repo=repo)

    # Default: derive the graph file path from the workspace config.
    root = Path(workspace) if workspace is not None else Path.cwd()
    ctx = build_context(root)
    graph_path = ctx.paths.data_dir / "graph.json"
    default_repo = JsonRepository(graph_path)
    loaded = default_repo.load()
    log = JsonlTransactionLog(ctx.paths.data_dir / "transactions.jsonl")
    gw = build_gateway(loaded, payload_validator=payload_validator, transaction_log=log)
    return EpistemeClient(gw, repo=default_repo)


def _without_none(**payload: object) -> dict[str, object]:
    """Return a copy of *payload* with all ``None`` values removed."""
    return {k: v for k, v in payload.items() if v is not None}


__all__ = ["EpistemeClient", "_without_none", "connect"]
