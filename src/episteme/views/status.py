"""Project-status read model, snapshot builder, and serialization.

Computes a compact summary of an epistemic graph suitable for dashboards,
AI agent context, and MCP status responses.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from ..epistemic.ports import EpistemicGraphPort
from .metrics import GraphMetrics


# ── Read model ───────────────────────────────────────────────────


@dataclass
class ProjectStatus:
    """High-level project status snapshot.

    Suitable for any consumer that needs a compact summary of a loaded
    epistemic graph.

    Attributes:
        project_name: Display name of the project.
        location: Optional deployment-specific location label.
        metrics: Full ``GraphMetrics`` snapshot.
        health_summary: One of ``"HEALTHY"``, ``"WARNINGS"``, or
            ``"CRITICAL"``.
        governance_session: Current governance session number if
            governance mode is enabled, otherwise ``None``.
        extra: Arbitrary additional metadata for extensibility.
    """

    project_name: str
    location: str
    metrics: GraphMetrics
    health_summary: str
    governance_session: int | None
    extra: dict[str, object] = field(default_factory=dict)


# ── Snapshot builder ─────────────────────────────────────────────


def get_status(
    graph: EpistemicGraphPort,
    *,
    project_name: str = "",
    location: str = "",
    health_summary: str = "",
    governance_session: int | None = None,
    extra: Mapping[str, object] | None = None,
) -> ProjectStatus:
    """Build a full project status snapshot.

    Computes metrics and assembles a ``ProjectStatus`` from an already-
    loaded graph plus optional caller-supplied metadata.

    Args:
        graph: The epistemic graph to snapshot.
        project_name: Optional display name supplied by the caller.
        location: Optional deployment-specific location label.
        health_summary: Optional pre-computed health summary label.
        governance_session: Optional governance session number.
        extra: Optional additional metadata.

    Returns:
        ProjectStatus: The assembled project status.

    Raises:
        NotImplementedError: Not yet implemented.

    """
    raise NotImplementedError


# ── Serialization ────────────────────────────────────────────────


def format_status_dict(status: ProjectStatus) -> dict:
    """Serialize a ``ProjectStatus`` to a plain primitive mapping.

    Converts dataclass fields to transport-friendly primitive values.

    Args:
        status: The project status to serialize.

    Returns:
        dict: A primitive representation of the status.

    Raises:
        NotImplementedError: Not yet implemented.

    """
    raise NotImplementedError


__all__ = ["ProjectStatus", "format_status_dict", "get_status"]
