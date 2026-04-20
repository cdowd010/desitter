"""Artifact-oriented export and rendering protocols."""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Protocol

from ._ports_graph import EpistemicGraphPort


@dataclass(frozen=True)
class Artifact:
    """Portable artifact emitted by a renderer or exporter.

    Artifacts are self-contained, transport-friendly objects that carry
    their content alongside metadata. Consumers (``ArtifactSink``
    implementations) decide what to do with them. Write to disk, stream
    to a client, embed in a report, etc.

    Attributes:
        name: Human-readable name for this artifact (e.g. a filename
            or section identifier such as ``"claims_table.md"`` or
            ``"web_export.json"``).
        content: The artifact's body. Type depends on the renderer or
            exporter: commonly ``str`` for text, ``bytes`` for binary,
            or a plain dict for structured data.
        media_type: IANA media type string (e.g. ``"text/markdown"`` or
            ``"application/json"``), or ``None`` if unspecified.
        metadata: Optional key-value metadata for consumers (e.g.
            generation timestamp, source entity IDs, version tag).
    """

    name: str
    content: object
    media_type: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)


class ArtifactSink(Protocol):
    """Consume a stream of artifacts produced by a renderer or exporter.

    Implementations decide how to handle each artifact: write to disk,
    push to an object store, embed in an in-memory report, etc. The
    control plane calls ``emit`` once per rendering or export pass.
    """

    def emit(self, artifacts: Iterable[Artifact]) -> None:
        """Consume a stream of artifacts.

        Args:
            artifacts: An iterable of ``Artifact`` instances to consume.
                Iterating this may trigger I/O in the producer.
        """
        ...


class GraphExporter(Protocol):
    """Produce portable data artifacts from the epistemic graph.

    Exporters serialize the graph into a transport format (e.g. JSON,
    CSV) via a stream of ``Artifact`` instances. The implementation
    decides the format; the control-plane ``export`` function handles
    routing to an ``ArtifactSink``.
    """

    def export(self, graph: EpistemicGraphPort) -> Iterable[Artifact]:
        """Serialize the graph into a stream of portable artifacts.

        Args:
            graph: The epistemic graph to export.

        Returns:
            Iterable[Artifact]: A stream of serialized artifacts. May
                be lazy (generator) or eagerly materialized.
        """
        ...


class GraphRenderer(Protocol):
    """Generate human-readable artifacts from the epistemic graph.

    Renderers produce markdown tables, summary views, or other
    human-readable formats from the graph. The control-plane ``render_all``
    function calls the renderer and passes results to an ``ArtifactSink``
    or cache layer.
    """

    def render(self, graph: EpistemicGraphPort) -> Iterable[Artifact]:
        """Return rendered artifacts ready for an ``ArtifactSink``.

        Args:
            graph: The epistemic graph to render.

        Returns:
            Iterable[Artifact]: A stream of rendered artifacts (e.g.
                one per markdown section or output file).
        """
        ...


__all__ = ["Artifact", "ArtifactSink", "GraphExporter", "GraphRenderer"]