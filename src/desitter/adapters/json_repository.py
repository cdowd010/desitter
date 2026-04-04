"""JSON-backed implementation of WebRepository.

Loads and saves the epistemic web as a collection of JSON files under
project/data/. Each entity type has its own file:
  claims.json, assumptions.json, predictions.json, analyses.json,
  independence_groups.json, theories.json, discoveries.json,
  dead_ends.json, concepts.json, parameters.json

Implements the WebRepository protocol from epistemic/ports.py.
"""
from __future__ import annotations

import json
from pathlib import Path

from ..epistemic.web import EpistemicWeb


class JsonRepository:
    """Loads and saves the epistemic web as JSON files on disk.

    data_dir: the project/data/ directory containing entity JSON files.
    """

    def __init__(self, data_dir: Path) -> None:
        """Create a repository bound to a project data directory.

        Args:
            data_dir: Directory containing per-entity JSON files.
        """
        self._data_dir = data_dir

    def load(self) -> EpistemicWeb:
        """Deserialise all entity JSON files and return a fully hydrated EpistemicWeb.

        Missing files are treated as empty registries (not an error).
        """
        raise NotImplementedError

    def save(self, web: EpistemicWeb) -> None:
        """Serialise the web to JSON files, one per entity type.

        Writes atomically (write to temp file, then rename) to avoid
        partial writes on crash.
        """
        raise NotImplementedError

    def _load_file(self, name: str) -> list[dict]:
        """Read and parse a single entity JSON file.

        Returns an empty list if the file doesn't exist.
        """
        path = self._data_dir / name
        if not path.exists():
            return []
        return json.loads(path.read_text(encoding="utf-8"))

    def _write_file(self, name: str, data: list[dict]) -> None:
        """Write entity data to a JSON file atomically."""
        path = self._data_dir / name
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(data, indent=2, default=str, ensure_ascii=False),
            encoding="utf-8",
        )
        tmp.replace(path)
