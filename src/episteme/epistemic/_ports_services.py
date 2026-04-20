"""Service protocols that act on an epistemic graph."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

from ._ports_graph import EpistemicGraphPort
from .types import Finding


class GraphValidator(Protocol):
    """Validate an epistemic graph and return a structured finding list.

    Implementations may run domain invariant checks (``DomainValidator``)
    or deployment-specific structural checks. Multiple validators can be
    composed via ``validate_project``.
    """

    def validate(self, graph: EpistemicGraphPort) -> list[Finding]:
        """Run all validation rules and return findings.

        Args:
            graph: The epistemic graph to validate.

        Returns:
            list[Finding]: Zero or more findings describing integrity
                violations. An empty list means no issues were found.
        """
        ...


class ProseSync(Protocol):
    """Update managed-prose blocks derived from canonical epistemic state.

    Implementations know which prose blocks exist (e.g. generated
    markdown sections in the repository) and how to write them. The
    control-plane functions in ``prose.py`` depend on this protocol so
    that filesystem I/O stays out of the control plane.
    """

    def sync(
        self,
        graph: EpistemicGraphPort,
        *,
        dry_run: bool = False,
    ) -> dict[str, object]:
        """Update managed prose blocks to match canonical state.

        Args:
            graph: The epistemic graph to derive prose from.
            dry_run: When ``True``, compute changes but do not write
                anything to disk.

        Returns:
            dict[str, object]: A summary of which blocks were (or would
                be) updated, keyed by block name.
        """
        ...

    def verify(self, graph: EpistemicGraphPort) -> list[Finding]:
        """Report prose blocks that have drifted from canonical state.

        Args:
            graph: The epistemic graph to check against.

        Returns:
            list[Finding]: One finding per block whose on-disk content
                differs from what the graph would generate.
        """
        ...


class TransactionLog(Protocol):
    """Append-only provenance log for gateway mutations.

    Each successful gateway mutation records an entry so that external
    tools can watch, index, or react to state changes. The implementation
    decides the storage format (e.g. ``transaction_log.jsonl``).
    """

    def append(self, operation: str, identifier: str) -> str:
        """Record a completed operation and return its transaction ID.

        Args:
            operation: Human-readable operation name, e.g.
                ``"register_claim"``.
            identifier: The primary entity ID affected by the operation.

        Returns:
            str: A unique transaction ID for this log entry (e.g. a
                UUID or monotonic counter string).
        """
        ...


class PayloadValidator(Protocol):
    """Validate inbound mutation payloads before the gateway mutates the graph.

    Implementations perform schema checks against the declared payload
    structure for each resource type. The gateway calls this before
    constructing domain entities, so type errors surface as structured
    ``Finding`` lists rather than Python exceptions.
    """

    def validate(self, resource: str, payload: Mapping[str, object]) -> list[Finding]:
        """Return findings describing schema or structural issues, if any.

        Args:
            resource: Canonical resource key (e.g. ``"claim"``,
                ``"prediction"``).
            payload: The inbound mutation payload to validate.

        Returns:
            list[Finding]: Zero or more schema or type findings. An
                empty list means the payload passed all checks.
        """
        ...


__all__ = ["PayloadValidator", "ProseSync", "TransactionLog", "GraphValidator"]