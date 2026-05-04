"""Composition root for gateway construction.

``build_gateway`` is the single place that wires an epistemic graph and
optional abstract dependencies (``GraphValidator``, ``PayloadValidator``)
into a ``Gateway``.

Persistence (``GraphRepository``) is NOT wired here. It belongs to
``EpistemeClient``, which owns all persistence decisions.
"""
from __future__ import annotations

from ..epistemic.ports import EpistemicGraphPort, PayloadValidator
from .gateway import Gateway
from .validate import DomainValidator


def build_gateway(
    graph: EpistemicGraphPort,
    *,
    payload_validator: PayloadValidator | None = None,
) -> Gateway:
    """Construct a ``Gateway`` around an epistemic-graph implementation.

    This is the single composition root for gateway construction.
    Callers supply a pre-loaded (or empty) graph and optionally inject
    dependencies. When ``payload_validator`` is ``None``, no payload
    validation is performed before mutations.

    Args:
        graph: The epistemic graph the gateway will hold.
        payload_validator: Optional payload validator implementation.
            If ``None``, gateway mutations skip schema pre-validation.

    Returns:
        Gateway: A ready-to-use gateway owning the given graph.
    """
    validator = DomainValidator()
    return Gateway(graph, validator, payload_validator=payload_validator)
