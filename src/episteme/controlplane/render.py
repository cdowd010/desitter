"""Generated view surfaces with incremental SHA-256 caching.

Orchestrates the rendering of an epistemic graph into human-readable files
(markdown tables, summary views, etc.). Only re-renders surfaces whose
input fingerprint has changed since the last run.

This module performs I/O (cache reads/writes, file output) and therefore
lives in the control plane rather than the read-only views layer.

Does NOT mutate the epistemic graph.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ..epistemic.ports import EpistemicGraphPort, GraphRenderer


def compute_fingerprint(graph: EpistemicGraphPort) -> str:
    """Compute a SHA-256 fingerprint of the graph's serializable state.

    Used by ``render_all`` to decide whether re-rendering is needed.
    The fingerprint changes when any entity in the graph is added,
    removed, or modified.

    Args:
        graph: The epistemic graph to fingerprint.

    Returns:
        str: A hex-encoded SHA-256 digest.

    Raises:
        NotImplementedError: Not yet implemented.
    """
    raise NotImplementedError


def load_render_cache(cache_path: Path) -> dict[str, str]:
    """Load the ``{surface_name: last_fingerprint}`` cache from disk.

    Args:
        cache_path: Path to the render fingerprint cache JSON file.

    Returns:
        dict[str, str]: The cached fingerprints. Returns an empty dict
            if the cache file does not exist.

    Raises:
        NotImplementedError: Not yet implemented.
    """
    raise NotImplementedError


def save_render_cache(cache_path: Path, cache: dict[str, str]) -> None:
    """Persist the render cache to disk.

    Args:
        cache_path: Path to the render fingerprint cache JSON file.
        cache: The ``{surface_name: fingerprint}`` mapping to persist.

    Raises:
        NotImplementedError: Not yet implemented.
    """
    raise NotImplementedError


def render_all(
    graph: EpistemicGraphPort,
    renderer: GraphRenderer,
    *,
    output_dir: Path | None = None,
    cache_path: Path | None = None,
    force: bool = False,
) -> dict[str, bool]:
    """Render all surfaces, skipping unchanged ones unless ``force=True``.

    Computes the graph's fingerprint, compares it against the cached
    fingerprint for each surface, and only re-renders surfaces whose
    input has changed. Updates the cache after rendering.

    Args:
        graph: The epistemic graph to render.
        renderer: The view renderer that produces markdown surfaces.
        output_dir: Directory to write rendered files. If ``None``,
            surfaces are returned but not written to disk.
        cache_path: Path to the render fingerprint cache file. If
            ``None``, caching is skipped and all surfaces are rendered.
        force: If ``True``, re-render all surfaces regardless of cache.

    Returns:
        dict[str, bool]: ``{surface_name: was_written}`` for each surface.

    Raises:
        NotImplementedError: Not yet implemented.
    """
    raise NotImplementedError
