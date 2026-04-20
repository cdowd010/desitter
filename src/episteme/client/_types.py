"""Client-facing result and error types.

These types define the public client contract independently from the
client orchestration and resource helper surfaces.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Generic, TypeVar

from ..epistemic.types import Finding


ResultData = TypeVar("ResultData")


@dataclass(frozen=True)
class ClientResult(Generic[ResultData]):
    """Typed wrapper over a gateway result returned by every client operation.

    Callers inspect ``status`` to determine success or failure before
    reading ``data``. No client operation raises ``EpistemeClientError``
    by default; that behaviour must be explicitly requested.

    Attributes:
        status: Outcome of the operation. Mirrors ``GatewayResult.status``.
            Common values: ``"ok"`` (success), ``"BLOCKED"`` (domain
            invariant blocked the write), ``"error"`` (bad input).
        changed: ``True`` when the in-memory graph was modified. Always
            ``False`` for ``dry_run=True`` calls and read operations.
        message: Human-readable summary of the outcome.
        findings: Structured findings produced during the operation
            (schema violations, invariant failures, coverage warnings).
            Empty for successful non-validating operations.
        transaction_id: Opaque string from the transaction log for
            successful mutations, or ``None``.
        data: The typed operation output: a domain entity for ``get``
            and mutation operations; a list for ``list``; a dict for
            ``query``. ``None`` for error results.
    """

    status: str
    changed: bool
    message: str
    findings: list[Finding] = field(default_factory=list)
    transaction_id: str | None = None
    data: ResultData | None = None


class EpistemeClientError(Exception):
    """Raised when the gateway returns a non-success status.

    Not raised by default — callers must opt in to this behaviour.
    When raised, the ``status``, ``message``, and ``findings`` fields
    carry the same information that would appear in a ``ClientResult``.

    Attributes:
        status: The gateway status string that triggered the error
            (e.g. ``"BLOCKED"`` or ``"error"``).\n        message: Human-readable error description.
        findings: Structured findings associated with the error, if any.
    """

    def __init__(
        self,
        status: str,
        message: str,
        findings: list[Finding] | None = None,
    ) -> None:
        """Initialize a client error.

        Args:
            status: The gateway status that triggered this error.
            message: Human-readable description of the failure.
            findings: Optional structured findings from the gateway
                (schema violations, invariant failures, etc.).
        """
        super().__init__(message)
        self.status = status
        self.message = message
        self.findings = findings or []


__all__ = ["ClientResult", "EpistemeClientError"]
