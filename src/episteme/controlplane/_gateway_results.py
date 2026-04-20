"""Gateway result types."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from ..epistemic.types import Finding


@dataclass
class GatewayResult:
    """Stable result envelope returned by every gateway operation.

    Every public method on ``Gateway`` returns a ``GatewayResult``
    and never raises. Callers inspect ``status`` to determine success
    or failure before reading ``data``.

    Attributes:
        status: Outcome of the operation. Common values:
            ``"ok"``: success; ``"BLOCKED"``: domain invariant
            violation blocked the mutation; ``"error"``. Bad input
            (unknown resource, broken reference, missing required field).
        changed: ``True`` when the in-memory graph was modified as a result
            of this operation. Always ``False`` for ``dry_run=True`` calls
            and for read operations (``get``, ``list``, ``query``).
        message: Human-readable summary of the outcome. Suitable for
            logging or returning to a caller via CLI/MCP.
        findings: Structured findings produced during the operation
            (schema violations, invariant failures, coverage warnings,
            etc.). Always empty for successful non-validating operations.
        transaction_id: Opaque string produced by the ``TransactionLog``
            if one is configured, or ``None``. Uniquely identifies this
            mutation in the append-only log.
        data: Operation-specific result payload. ``get`` returns
            ``{"resource": {...}}``. ``list`` returns
            ``{"items": [...], "count": N}``. ``query`` returns
            the serialized query result. ``None`` for mutations.
    """

    status: str
    changed: bool
    message: str
    findings: list[Finding] = field(default_factory=list)
    transaction_id: str | None = None
    data: Mapping[str, object] | None = None


__all__ = ["GatewayResult"]