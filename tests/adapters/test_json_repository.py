"""Tests for adapters/json_repository.py — _load_file and _write_file."""
from __future__ import annotations

import json

import pytest

from desitter.adapters.json_repository import JsonRepository


class TestLoadFile:
    def test_missing_file_returns_empty(self, tmp_path):
        repo = JsonRepository(tmp_path)
        result = repo._load_file("nonexistent.json")
        assert result == []

    def test_valid_json_file(self, tmp_path):
        data = [{"id": "C-001", "statement": "x"}]
        (tmp_path / "claims.json").write_text(json.dumps(data), encoding="utf-8")
        repo = JsonRepository(tmp_path)
        result = repo._load_file("claims.json")
        assert result == data

    def test_empty_list(self, tmp_path):
        (tmp_path / "empty.json").write_text("[]", encoding="utf-8")
        repo = JsonRepository(tmp_path)
        assert repo._load_file("empty.json") == []

    def test_invalid_json_raises(self, tmp_path):
        (tmp_path / "bad.json").write_text("{not valid json", encoding="utf-8")
        repo = JsonRepository(tmp_path)
        with pytest.raises(json.JSONDecodeError):
            repo._load_file("bad.json")


class TestWriteFile:
    def test_creates_file(self, tmp_path):
        repo = JsonRepository(tmp_path)
        data = [{"id": "C-001"}]
        repo._write_file("out.json", data)
        assert (tmp_path / "out.json").exists()
        loaded = json.loads((tmp_path / "out.json").read_text())
        assert loaded == data

    def test_atomic_write_no_tmp_left(self, tmp_path):
        repo = JsonRepository(tmp_path)
        repo._write_file("out.json", [{"a": 1}])
        assert not (tmp_path / "out.json.tmp").exists()

    def test_overwrites_existing(self, tmp_path):
        repo = JsonRepository(tmp_path)
        repo._write_file("out.json", [{"v": 1}])
        repo._write_file("out.json", [{"v": 2}])
        loaded = json.loads((tmp_path / "out.json").read_text())
        assert loaded == [{"v": 2}]

    def test_roundtrip(self, tmp_path):
        repo = JsonRepository(tmp_path)
        original = [{"id": f"item-{i}", "val": i} for i in range(5)]
        repo._write_file("data.json", original)
        loaded = repo._load_file("data.json")
        assert loaded == original
