"""Bulk export orchestration.

Produces self-contained exports of the epistemic graph via a pluggable
``GraphExporter`` and ``ArtifactSink``. Exports are point-in-time
snapshots — they do not affect canonical state.
"""
from __future__ import annotations

from ..epistemic.ports import ArtifactSink, EpistemicGraphPort, GraphExporter


def export(
    graph: EpistemicGraphPort,
    exporter: GraphExporter,
    sink: ArtifactSink,
) -> None:
    """Export the graph using the provided exporter.

    Delegates artifact production to *exporter* and delivery to *sink*.

    Args:
        graph: The epistemic graph to export.
        exporter: A ``GraphExporter`` implementation that produces export
            artifacts.
        sink: An ``ArtifactSink`` implementation that consumes those
            artifacts.

    Raises:
        NotImplementedError: Not yet implemented.
    """
    raise NotImplementedError
