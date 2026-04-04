"""Tests for config.py — HorizonConfig, ProjectPaths, ProjectContext, load_config, build_context."""
from __future__ import annotations

from pathlib import Path

import pytest

from horizon_research.config import (
    HorizonConfig,
    ProjectContext,
    ProjectPaths,
    build_context,
    load_config,
)


class TestHorizonConfig:
    def test_defaults(self):
        cfg = HorizonConfig()
        assert cfg.project_dir == Path("project")

    def test_custom_project_dir(self):
        cfg = HorizonConfig(project_dir=Path("custom"))
        assert cfg.project_dir == Path("custom")


class TestLoadConfig:
    def test_missing_file_returns_defaults(self, tmp_path):
        cfg = load_config(tmp_path)
        assert cfg.project_dir == Path("project")

    def test_empty_toml(self, tmp_path):
        (tmp_path / "horizon.toml").write_text("", encoding="utf-8")
        cfg = load_config(tmp_path)
        assert cfg.project_dir == Path("project")

    def test_custom_project_dir(self, tmp_path):
        (tmp_path / "horizon.toml").write_text(
            '[horizon]\nproject_dir = "my_project"\n', encoding="utf-8"
        )
        cfg = load_config(tmp_path)
        assert cfg.project_dir == Path("my_project")

    def test_missing_horizon_section(self, tmp_path):
        (tmp_path / "horizon.toml").write_text(
            "[other]\nkey = 1\n", encoding="utf-8"
        )
        cfg = load_config(tmp_path)
        assert cfg.project_dir == Path("project")


class TestBuildContext:
    def test_path_derivation(self, tmp_path):
        cfg = HorizonConfig(project_dir=Path("proj"))
        ctx = build_context(tmp_path, cfg)
        assert ctx.workspace == tmp_path
        assert ctx.config is cfg
        assert ctx.paths.project_dir == tmp_path / "proj"
        assert ctx.paths.data_dir == tmp_path / "proj" / "data"
        assert ctx.paths.views_dir == tmp_path / "proj" / "views"
        assert ctx.paths.cache_dir == tmp_path / "proj" / ".cache"
        assert ctx.paths.render_cache_file == tmp_path / "proj" / ".cache" / "render.json"
        assert ctx.paths.transaction_log_file == tmp_path / "proj" / "data" / "transaction_log.jsonl"

    def test_default_config(self, tmp_path):
        ctx = build_context(tmp_path, HorizonConfig())
        assert ctx.paths.project_dir == tmp_path / "project"
