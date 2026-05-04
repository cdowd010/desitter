"""JSON-file-backed graph repository.

Implements the ``GraphRepository`` protocol using a single JSON file on
the local filesystem. Serialization is a plain dict with one key per
entity collection; each collection is a list of serialized entity dicts.

The file format is::

    {
      "version": <int>,
      "hypotheses": [{...}, ...],
      "assumptions": [{...}, ...],
      ...
    }

``save`` writes atomically via a temp-file rename so a crash mid-write
cannot leave a corrupt graph file.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from ..epistemic.codec import build_entity, entity_to_dict
from ..epistemic.graph import EpistemicGraph
from ..epistemic._ports_graph import EpistemicGraphPort
from ..epistemic.model import (
    Analysis,
    Assumption,
    DeadEnd,
    Discovery,
    Experiment,
    Hypothesis,
    IndependenceGroup,
    Objective,
    Observation,
    PairwiseSeparation,
    Parameter,
    Prediction,
)
from ..epistemic.types import (
    AnalysisId,
    AssumptionId,
    DeadEndId,
    DiscoveryId,
    ExperimentId,
    HypothesisId,
    IndependenceGroupId,
    ObjectiveId,
    ObservationId,
    PairwiseSeparationId,
    ParameterId,
    PredictionId,
)

# Maps resource name → (collection attribute on EpistemicGraph, entity class).
# Order here is irrelevant for load (we bypass register_* for direct construction)
# and for save (we iterate all collections).
_COLLECTIONS: list[tuple[str, str, type]] = [
    ("parameter",           "parameters",           Parameter),
    ("assumption",          "assumptions",          Assumption),
    ("analysis",            "analyses",             Analysis),
    ("objective",           "objectives",           Objective),
    ("hypothesis",          "hypotheses",           Hypothesis),
    ("prediction",          "predictions",          Prediction),
    ("dead_end",            "dead_ends",            DeadEnd),
    ("independence_group",  "independence_groups",  IndependenceGroup),
    ("pairwise_separation", "pairwise_separations", PairwiseSeparation),
    ("discovery",           "discoveries",          Discovery),
    ("experiment",          "experiments",          Experiment),
    ("observation",         "observations",         Observation),
]


class JsonRepository:
    """``GraphRepository`` backed by a single JSON file.

    Attributes are persisted as a snapshot: every entity in every
    collection is serialized including backlink fields. Loading
    reconstructs the exact graph state by directly populating
    ``EpistemicGraph`` fields rather than replaying ``register_*``
    calls, so topological order is irrelevant and backlinks are
    restored without duplication.

    Args:
        path: Path to the JSON file. The file and any parent directories
            are created on the first ``save`` call. If the file does not
            exist when ``load`` is called an empty ``EpistemicGraph`` is
            returned.
    """

    def __init__(self, path: Path | str) -> None:
        self._path = Path(path)

    @property
    def supports_native_validation(self) -> bool:
        return False

    # ── GraphRepository protocol ───────────────────────────────────

    def load(self) -> EpistemicGraph:
        """Deserialize and return the full epistemic graph from the JSON file.

        Returns:
            EpistemicGraph: The fully hydrated graph. Returns an empty
                graph (version 0, no entities) if the file does not exist.

        Raises:
            json.JSONDecodeError: If the file contents are not valid JSON.
            KeyError: If an entity dict references an unknown resource type.
        """
        if not self._path.exists():
            return EpistemicGraph()

        raw: dict[str, Any] = json.loads(
            self._path.read_text(encoding="utf-8")
        )

        version = int(raw.get("version", 0))

        # Deserialize each collection.  We build typed-ID-keyed dicts and
        # pass them directly to the EpistemicGraph dataclass constructor,
        # bypassing register_* so that:
        #   - topological ordering is not required, and
        #   - backlink fields (e.g. assumption.used_in_hypotheses) are
        #     restored as-saved rather than re-derived (which would double them).
        kwargs: dict[str, Any] = {"version": version}
        for resource, attr, _cls in _COLLECTIONS:
            entries: list[dict[str, Any]] = raw.get(attr, [])
            typed: dict[Any, Any] = {}
            for entry in entries:
                entity = build_entity(resource, entry)
                typed[getattr(entity, "id")] = entity  # type: ignore[arg-type]
            kwargs[attr] = typed

        return EpistemicGraph(**kwargs)

    def save(self, graph: EpistemicGraphPort) -> None:
        """Serialize and atomically write the graph to the JSON file.

        The file is written to a sibling ``.tmp`` file first, then
        renamed over the target. This ensures a crash mid-write cannot
        leave a partial or corrupt file.

        Args:
            graph: The graph to persist. Any object conforming to
                ``EpistemicGraphPort`` is accepted.

        Raises:
            OSError: If the file cannot be written (permissions, disk full, …).
        """
        data: dict[str, Any] = {"version": graph.version}

        for _resource, attr, _cls in _COLLECTIONS:
            collection = getattr(graph, attr)
            data[attr] = [
                entity_to_dict(entity) for entity in collection.values()
            ]

        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        os.replace(tmp, self._path)
