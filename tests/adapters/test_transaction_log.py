"""Tests for JsonlTransactionLog.

Coverage:
- append returns a non-empty string (transaction_id)
- append creates the log file (and parent directories)
- each call appends a new line
- each line is valid JSON
- JSON entry contains transaction_id, operation, identifier, timestamp
- two consecutive calls return different transaction_ids
- entries are appended, not overwritten
- timestamp is an ISO-8601 UTC string
- transaction_id is a valid UUID4
"""
from __future__ import annotations

import json
import re
import uuid

import pytest

from episteme.adapters.transaction_log import JsonlTransactionLog


# ── append: return value ──────────────────────────────────────────


def test_append_returns_nonempty_string(tmp_path):
    log = JsonlTransactionLog(tmp_path / "ops.jsonl")
    tid = log.append("register_hypothesis", "H-001")
    assert isinstance(tid, str)
    assert len(tid) > 0


def test_append_returns_valid_uuid4(tmp_path):
    log = JsonlTransactionLog(tmp_path / "ops.jsonl")
    tid = log.append("register_hypothesis", "H-001")
    parsed = uuid.UUID(tid)
    assert parsed.version == 4


# ── append: file creation ─────────────────────────────────────────


def test_append_creates_log_file(tmp_path):
    path = tmp_path / "ops.jsonl"
    log = JsonlTransactionLog(path)
    log.append("register_hypothesis", "H-001")
    assert path.exists()


def test_append_creates_parent_directories(tmp_path):
    path = tmp_path / "a" / "b" / "ops.jsonl"
    JsonlTransactionLog(path).append("register_hypothesis", "H-001")
    assert path.exists()


# ── append: file contents ─────────────────────────────────────────


def test_each_line_is_valid_json(tmp_path):
    path = tmp_path / "ops.jsonl"
    log = JsonlTransactionLog(path)
    log.append("register_hypothesis", "H-001")
    log.append("transition_prediction", "P-003")
    lines = path.read_text().strip().splitlines()
    assert len(lines) == 2
    for line in lines:
        json.loads(line)  # must not raise


def test_entry_contains_required_keys(tmp_path):
    path = tmp_path / "ops.jsonl"
    JsonlTransactionLog(path).append("register_assumption", "A-002")
    entry = json.loads(path.read_text().strip())
    assert "transaction_id" in entry
    assert "operation" in entry
    assert "identifier" in entry
    assert "timestamp" in entry


def test_entry_operation_and_identifier_match(tmp_path):
    path = tmp_path / "ops.jsonl"
    JsonlTransactionLog(path).append("update_hypothesis", "H-007")
    entry = json.loads(path.read_text().strip())
    assert entry["operation"] == "update_hypothesis"
    assert entry["identifier"] == "H-007"


def test_entry_transaction_id_matches_return_value(tmp_path):
    path = tmp_path / "ops.jsonl"
    log = JsonlTransactionLog(path)
    tid = log.append("register_hypothesis", "H-001")
    entry = json.loads(path.read_text().strip())
    assert entry["transaction_id"] == tid


# ── append: consecutive calls ─────────────────────────────────────


def test_two_calls_return_different_transaction_ids(tmp_path):
    log = JsonlTransactionLog(tmp_path / "ops.jsonl")
    t1 = log.append("register_hypothesis", "H-001")
    t2 = log.append("register_hypothesis", "H-002")
    assert t1 != t2


def test_entries_are_appended_not_overwritten(tmp_path):
    path = tmp_path / "ops.jsonl"
    log = JsonlTransactionLog(path)
    log.append("register_hypothesis", "H-001")
    log.append("register_assumption", "A-001")
    log.append("register_prediction", "P-001")
    lines = path.read_text().strip().splitlines()
    assert len(lines) == 3


def test_entry_order_matches_append_order(tmp_path):
    path = tmp_path / "ops.jsonl"
    log = JsonlTransactionLog(path)
    log.append("op_first", "E-001")
    log.append("op_second", "E-002")
    lines = path.read_text().strip().splitlines()
    first = json.loads(lines[0])
    second = json.loads(lines[1])
    assert first["operation"] == "op_first"
    assert second["operation"] == "op_second"


# ── append: timestamp ─────────────────────────────────────────────


def test_timestamp_is_iso8601_utc(tmp_path):
    path = tmp_path / "ops.jsonl"
    JsonlTransactionLog(path).append("register_hypothesis", "H-001")
    entry = json.loads(path.read_text().strip())
    ts = entry["timestamp"]
    # Must end with +00:00 (UTC) per datetime.isoformat() with utc timezone
    assert ts.endswith("+00:00")
    # Must be parseable as ISO 8601
    from datetime import datetime, timezone
    parsed = datetime.fromisoformat(ts)
    assert parsed.tzinfo is not None
