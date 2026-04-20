"""Epistemic-graph metric read models and computation.

Pure functions. No I/O, no side effects. Counts entities, computes
detailed prediction statistics, and identifies coverage gaps.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..epistemic.ports import EpistemicGraphPort


# ── Read models ──────────────────────────────────────────────────


@dataclass
class PredictionMetrics:
    """Aggregate statistics for predictions.

    Attributes:
        total: Total number of predictions in the graph.
        by_status: Count of predictions per ``PredictionStatus`` value.
        by_tier: Count of predictions per ``ConfidenceTier`` value.
        tier_a_confirmed: Number of Tier-A predictions with
            ``CONFIRMED`` status.
        tier_a_total: Total number of Tier-A predictions.
        stressed: IDs of predictions under epistemic stress (e.g.
            assumptions retracted or hypotheses refuted).
    """

    total: int = 0
    by_status: dict[str, int] = field(default_factory=dict)
    by_tier: dict[str, int] = field(default_factory=dict)
    tier_a_confirmed: int = 0
    tier_a_total: int = 0
    stressed: list[str] = field(default_factory=list)


@dataclass
class GraphMetrics:
    """Full metrics snapshot of an ``EpistemicGraph``.

    Provides entity counts for every collection plus detailed prediction
    metrics and coverage gap lists.

    Attributes:
        hypothesis_count: Number of hypotheses.
        assumption_count: Number of assumptions.
        analysis_count: Number of analyses.
        objective_count: Number of objectives.
        discovery_count: Number of discoveries.
        dead_end_count: Number of dead ends.
        parameter_count: Number of parameters.
        independence_group_count: Number of independence groups.
        pairwise_separation_count: Number of pairwise separations.
        prediction_metrics: Detailed prediction aggregate stats.
        uncovered_quantitative_hypotheses: IDs of numerical hypotheses that
            lack a covering prediction.
        empirical_assumptions_without_consequence: IDs of empirical
            assumptions that have no falsifiable consequence.
    """

    hypothesis_count: int = 0
    assumption_count: int = 0
    analysis_count: int = 0
    objective_count: int = 0
    discovery_count: int = 0
    dead_end_count: int = 0
    parameter_count: int = 0
    independence_group_count: int = 0
    pairwise_separation_count: int = 0
    prediction_metrics: PredictionMetrics = field(default_factory=PredictionMetrics)
    uncovered_quantitative_hypotheses: list[str] = field(default_factory=list)
    empirical_assumptions_without_consequence: list[str] = field(default_factory=list)


# ── Computation ──────────────────────────────────────────────────


def compute_metrics(graph: EpistemicGraphPort) -> GraphMetrics:
    """Compute aggregate metrics from the epistemic graph.

    Pure function. No I/O, no side effects. Counts entities in every
    collection, computes detailed prediction statistics, and identifies
    coverage gaps.

    Args:
        graph: The epistemic graph to analyze.

    Returns:
        GraphMetrics: A complete metrics snapshot.

    Raises:
        NotImplementedError: Not yet implemented.

    """
    raise NotImplementedError


def tier_a_evidence_summary(graph: EpistemicGraphPort) -> dict[str, object]:
    """Summarize Tier-A prediction evidence, flagging correlated groups.

    Identifies which Tier-A predictions share independence groups and
    flags groups where all confirmed predictions are correlated.
    Returns a dict suitable for inclusion in status output.

    Args:
        graph: The epistemic graph to analyze.

    Returns:
        dict[str, object]: Summary keyed by independence group with
            correlation flags and prediction details.

    Raises:
        NotImplementedError: Not yet implemented.

    """
    raise NotImplementedError


__all__ = [
    "PredictionMetrics",
    "GraphMetrics",
    "compute_metrics",
    "tier_a_evidence_summary",
]
