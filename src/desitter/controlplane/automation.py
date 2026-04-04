"""Declarative render/stale-trigger contracts.

Defines which control-plane operations should automatically trigger
downstream effects (e.g., re-rendering views when the web changes,
invalidating caches when a resource is registered).

This module owns no I/O. It describes *what* should happen; the gateway
and render services perform the actual work.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RenderTrigger:
    """Declares that a resource mutation should trigger a render pass.

    resource:   The canonical resource key that triggers the render.
    surfaces:   Which render surfaces to invalidate (None = all).
    """
    resource: str
    surfaces: list[str] | None = None


# Default trigger table: any write to these resources invalidates all views.
DEFAULT_RENDER_TRIGGERS: list[RenderTrigger] = [
    RenderTrigger("claim"),
    RenderTrigger("assumption"),
    RenderTrigger("prediction"),
    RenderTrigger("analysis"),
    RenderTrigger("independence_group"),
    RenderTrigger("theory"),
    RenderTrigger("discovery"),
    RenderTrigger("dead_end"),
    RenderTrigger("parameter"),
]


def should_render(resource: str, triggers: list[RenderTrigger] | None = None) -> bool:
    """Return True if a mutation to resource should trigger a render pass."""
    active = triggers if triggers is not None else DEFAULT_RENDER_TRIGGERS
    return any(t.resource == resource for t in active)
