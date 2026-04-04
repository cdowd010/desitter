"""Project configuration and runtime context.

This module is the single place for:
  - HorizonConfig    — parsed from horizon.toml (or defaults)
  - ProjectPaths     — all filesystem paths derived from workspace + config
  - ProjectContext   — the runtime contract passed to every service
  - load_config()    — reads horizon.toml, returns HorizonConfig
  - build_context()  — derives all paths, returns ProjectContext

Every service receives a ProjectContext. No service reads horizon.toml
directly — all config is injected via ProjectContext.

horizon.toml schema (all keys optional):

  [horizon]
  project_dir = "project"     # relative to workspace root
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

_CONFIG_FILENAME = "horizon.toml"


# ── User config (from horizon.toml) ──────────────────────────────

@dataclass
class HorizonConfig:
    """Parsed from horizon.toml. All fields have safe defaults."""
    project_dir: Path = field(default_factory=lambda: Path("project"))


# ── Filesystem paths ──────────────────────────────────────────────

@dataclass
class ProjectPaths:
    """All filesystem paths derived from workspace root and config.

    Computed once at context-build time. Never re-derived at call time.
    """
    workspace: Path
    project_dir: Path
    data_dir: Path           # entity JSON files (claims.json, predictions.json, ...)
    views_dir: Path          # rendered markdown outputs
    cache_dir: Path
    render_cache_file: Path
    transaction_log_file: Path


# ── Runtime contract ──────────────────────────────────────────────

@dataclass
class ProjectContext:
    """Runtime contract passed to every service.

    Immutable after construction. Services must not store mutable state
    on the context — use it to locate resources, then do work locally.
    """
    workspace: Path
    config: HorizonConfig
    paths: ProjectPaths


# ── Builders ──────────────────────────────────────────────────────

def load_config(workspace: Path) -> HorizonConfig:
    """Read horizon.toml from workspace and return a HorizonConfig.

    Missing file → all defaults. Missing keys → field defaults.
    """
    config_path = workspace / _CONFIG_FILENAME
    if not config_path.exists():
        return HorizonConfig()

    try:
        import tomllib          # Python 3.11+
    except ImportError:
        import tomli as tomllib  # type: ignore[no-redef]

    raw = tomllib.loads(config_path.read_text(encoding="utf-8"))
    horizon = raw.get("horizon", {})

    return HorizonConfig(
        project_dir=Path(horizon.get("project_dir", "project")),
    )


def build_context(workspace: Path, config: HorizonConfig) -> ProjectContext:
    """Derive all paths from workspace root and config. Return a ProjectContext.

    This is the only place path derivation logic lives.
    """
    project_dir = workspace / config.project_dir
    data_dir = project_dir / "data"
    cache_dir = project_dir / ".cache"

    paths = ProjectPaths(
        workspace=workspace,
        project_dir=project_dir,
        data_dir=data_dir,
        views_dir=project_dir / "views",
        cache_dir=cache_dir,
        render_cache_file=cache_dir / "render.json",
        transaction_log_file=data_dir / "transaction_log.jsonl",
    )
    return ProjectContext(workspace=workspace, config=config, paths=paths)
