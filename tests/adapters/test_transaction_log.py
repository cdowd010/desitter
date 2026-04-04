"""Tests for adapters/transaction_log.py — JsonTransactionLog."""
from __future__ import annotations

import json

import pytest

from horizon_research.adapters.transaction_log import JsonTransactionLog


class TestAppend:
    def test_creates_file_and_record(self, tmp_path):
        log_file = tmp_path / "sub" / "log.jsonl"
        log = JsonTransactionLog(log_file)
        tx_id = log.append("register", "C-001")
        assert log_file.exists()
        assert isinstance(tx_id, str)
        assert len(tx_id) > 0

    def test_record_schema(self, tmp_path):
        log = JsonTransactionLog(tmp_path / "log.jsonl")
        tx_id = log.append("register", "C-001")
        record = json.loads((tmp_path / "log.jsonl").read_text().strip())
        assert record["tx_id"] == tx_id
        assert record["operation"] == "register"
        assert record["identifier"] == "C-001"
        assert "timestamp" in record

    def test_multiple_appends(self, tmp_path):
        log = JsonTransactionLog(tmp_path / "log.jsonl")
        log.append("register", "C-001")
        log.append("update", "C-002")
        log.append("remove", "P-001")
        lines = (tmp_path / "log.jsonl").read_text().strip().splitlines()
        assert len(lines) == 3

    def test_unique_tx_ids(self, tmp_path):
        log = JsonTransactionLog(tmp_path / "log.jsonl")
        ids = {log.append("op", f"id-{i}") for i in range(10)}
        assert len(ids) == 10


class TestReadAll:
    def test_empty_when_missing(self, tmp_path):
        log = JsonTransactionLog(tmp_path / "nonexistent.jsonl")
        assert log.read_all() == []

    def test_roundtrip(self, tmp_path):
        log = JsonTransactionLog(tmp_path / "log.jsonl")
        log.append("register", "C-001")
        log.append("update", "C-002")
        records = log.read_all()
        assert len(records) == 2
        assert records[0]["operation"] == "register"
        assert records[1]["operation"] == "update"

    def test_preserves_order(self, tmp_path):
        log = JsonTransactionLog(tmp_path / "log.jsonl")
        for i in range(5):
            log.append("op", f"id-{i}")
        records = log.read_all()
        for i, rec in enumerate(records):
            assert rec["identifier"] == f"id-{i}"
