"""Managed-prose sync services.

Provides operations that keep human-readable prose blocks (e.g. generated
markdown sections) in sync with canonical epistemic state. These functions
depend on a ``ProseSync`` collaborator that owns the I/O and knows which
blocks exist.

Distinct from structural diagnostics (``check.py``): prose operations
carry a filesystem collaborator and have a write path (``sync_prose``).
"""
from __future__ import annotations

from ..epistemic.ports import EpistemicGraphPort, ProseSync
from ..epistemic.types import Finding


def sync_prose(
    graph: EpistemicGraphPort,
    syncer: ProseSync,
    *,
    dry_run: bool = False,
) -> dict[str, object]:
    """Update managed prose blocks derived from canonical state.

    Delegates to the provided ``syncer`` to bring prose blocks back in
    line with the epistemic graph. The syncer implementation decides which
    blocks exist and how they are written.

    Args:
        graph: The epistemic graph to derive prose from.
        syncer: A ``ProseSync`` implementation that owns the sync logic.
        dry_run: If ``True``, compute changes but do not write anything.

    Returns:
        dict[str, object]: A summary of which blocks were updated.

    Raises:
        NotImplementedError: Not yet implemented.
    """
    raise NotImplementedError


def verify_prose_sync(
    graph: EpistemicGraphPort,
    syncer: ProseSync,
) -> list[Finding]:
    """Assert that all managed prose blocks match canonical state.

    A read-only check that reports findings for any prose blocks that
    have drifted from the values the graph would generate.

    Args:
        graph: The epistemic graph to check against.
        syncer: A ``ProseSync`` implementation that owns the check logic.

    Returns:
        list[Finding]: Findings for any drifted blocks.

    Raises:
        NotImplementedError: Not yet implemented.
    """
    raise NotImplementedError


__all__ = ["sync_prose", "verify_prose_sync"]
