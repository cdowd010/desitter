"""Abstract interfaces the domain REQUIRES but does not IMPLEMENT.

Implemented by the adapters layer. Domain code programs against these
protocols, never against concrete classes.
"""
from __future__ import annotations

from typing import Protocol

from .types import Finding
from .web import EpistemicWeb


class WebRepository(Protocol):
    """Load and save the epistemic web."""

    def load(self) -> EpistemicWeb:
        """Deserialize and return the full epistemic web from storage."""
        ...

    def save(self, web: EpistemicWeb) -> None:
        """Serialize and persist the epistemic web to storage."""
        ...


class WebRenderer(Protocol):
    """Generate human-readable artifacts from the web."""

    def render(self, web: EpistemicWeb) -> dict[str, str]:
        """Return {relative_path: content} for all generated surfaces."""
        ...


class WebValidator(Protocol):
    """Validate the web and return findings."""

    def validate(self, web: EpistemicWeb) -> list[Finding]:
        """Run all validation rules and return a list of findings."""
        ...


class ProseSync(Protocol):
    """Update managed prose blocks derived from canonical state."""

    def sync(self, web: EpistemicWeb) -> dict[str, object]:
        """Sync prose blocks and return a summary of changes."""
        ...


class TransactionLog(Protocol):
    """Append provenance for gateway mutations and queries."""

    def append(self, operation: str, identifier: str) -> str:
        """Record an operation and return its transaction ID."""
        ...


class PayloadValidator(Protocol):
    """Validate inbound mutation payloads before the gateway mutates the web."""

    def validate(self, resource: str, payload: dict[str, object]) -> list[Finding]:
        """Return findings describing payload/schema issues, if any."""
        ...
