"""JSONL-backed append-only transaction log.

Each successful gateway mutation appends one JSON object to a ``.jsonl``
file.  Readers can tail the file, grep by operation name, or import it
into analytics tooling without parsing a monolithic JSON blob.

File format — one JSON object per line::

    {"transaction_id": "...", "operation": "register_hypothesis", "identifier": "H-001", "timestamp": "2024-01-15T10:30:00+00:00"}
    {"transaction_id": "...", "operation": "transition_prediction", "identifier": "P-003", "timestamp": "2024-01-15T10:31:42+00:00"}
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path


class JsonlTransactionLog:
    """``TransactionLog`` backed by a JSONL file.

    Entries are appended synchronously.  The file is opened in append
    mode for each write so the file descriptor is not held open between
    calls, which keeps the implementation simple and safe for concurrent
    readers.

    Args:
        path: Path to the ``.jsonl`` file.  The file and any parent
            directories are created on the first ``append`` call.
    """

    def __init__(self, path: Path | str) -> None:
        self._path = Path(path)

    # ── TransactionLog protocol ────────────────────────────────────

    def append(self, operation: str, identifier: str) -> str:
        """Record a completed operation and return its transaction ID.

        Args:
            operation: Human-readable operation name,
                e.g. ``"register_hypothesis"``.
            identifier: The primary entity ID affected by this operation.

        Returns:
            str: A UUID4 transaction ID unique to this log entry.
        """
        transaction_id = str(uuid.uuid4())
        entry = {
            "transaction_id": transaction_id,
            "operation": operation,
            "identifier": identifier,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")
        return transaction_id
