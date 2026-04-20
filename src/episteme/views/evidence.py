"""Per-hypothesis evidence summary view.

Assembles the full evidence picture for a single hypothesis: its
predictions with their statuses and observations, the assumption
foundation (with criticality and test coverage), linked analyses
and their staleness, and motivating objectives.

Pure function — no I/O, no side effects.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..epistemic.ports import EpistemicGraphPort
from ..epistemic.types import (
    AnalysisId,
    AssumptionId,
    ConfidenceTier,
    Criticality,
    EvidenceKind,
    HypothesisId,
    HypothesisStatus,
    MeasurementRegime,
    ObservationId,
    ObservationStatus,
    ObjectiveKind,
    PredictionId,
    PredictionStatus,
    ObjectiveId,
    ObjectiveStatus,
)


# ── Read models ──────────────────────────────────────────────────


@dataclass
class ObservationDetail:
    """Summary of a single observation bearing on a prediction.

    Attributes:
        id: Observation identifier.
        description: Human-readable description.
        status: Observation lifecycle status.
    """

    id: ObservationId
    description: str
    status: ObservationStatus


@dataclass
class PredictionDetail:
    """Evidence detail for a single prediction linked to the hypothesis.

    Attributes:
        id: Prediction identifier.
        observable: What is being measured or observed.
        status: Current lifecycle status.
        tier: Confidence classification.
        evidence_kind: Temporal/methodological classification.
        predicted: The predicted value or outcome.
        observed: The observed value (if any).
        observations: Observations bearing on this prediction.
    """

    id: PredictionId
    observable: str
    status: PredictionStatus
    tier: ConfidenceTier
    evidence_kind: EvidenceKind
    predicted: object
    observed: object
    observations: list[ObservationDetail] = field(default_factory=list)


@dataclass
class AssumptionDetail:
    """Evidence detail for an assumption in the hypothesis's foundation.

    Attributes:
        id: Assumption identifier.
        statement: Human-readable text.
        criticality: How load-bearing the assumption is.
        tested_by: Prediction IDs that explicitly test this assumption.
        direct: Whether the hypothesis directly references this
            assumption (as opposed to inheriting it transitively).
    """

    id: AssumptionId
    statement: str
    criticality: Criticality
    tested_by: list[PredictionId] = field(default_factory=list)
    direct: bool = True


@dataclass
class AnalysisDetail:
    """Evidence detail for a linked analysis.

    Attributes:
        id: Analysis identifier.
        has_result: Whether a result has been recorded.
        stale: Whether the analysis may be stale (a dependent parameter
            was modified after the last run).
    """

    id: AnalysisId
    has_result: bool
    stale: bool


@dataclass
class ObjectiveDetail:
    """Summary of a motivating objective.

    Attributes:
        id: Objective identifier.
        title: Human-readable name.
        kind: The type of objective.
        status: Current lifecycle status.
    """

    id: ObjectiveId
    title: str
    kind: ObjectiveKind
    status: ObjectiveStatus


@dataclass
class EvidenceSummary:
    """Complete evidence picture for a single hypothesis.

    Attributes:
        hypothesis_id: The hypothesis this summary describes.
        hypothesis_statement: The human-readable hypothesis text.
        hypothesis_status: Current lifecycle status.
        predictions: All predictions whose derivation chain includes
            this hypothesis, with observation details.
        assumptions: Full assumption foundation (direct and transitive),
            with criticality and test coverage.
        analyses: Linked analyses with staleness flags.
        objectives: Motivating objectives.
        confirmed_count: Number of predictions with CONFIRMED status.
        refuted_count: Number of predictions with REFUTED status.
        pending_count: Number of predictions with PENDING status.
        stressed_count: Number of predictions with STRESSED status.
        not_yet_testable_count: Number of predictions with NOT_YET_TESTABLE status.
        superseded_count: Number of predictions with SUPERSEDED status.
    """

    hypothesis_id: HypothesisId
    hypothesis_statement: str
    hypothesis_status: HypothesisStatus
    predictions: list[PredictionDetail] = field(default_factory=list)
    assumptions: list[AssumptionDetail] = field(default_factory=list)
    analyses: list[AnalysisDetail] = field(default_factory=list)
    objectives: list[ObjectiveDetail] = field(default_factory=list)
    confirmed_count: int = 0
    refuted_count: int = 0
    pending_count: int = 0
    stressed_count: int = 0
    not_yet_testable_count: int = 0
    superseded_count: int = 0


# ── Builder ──────────────────────────────────────────────────────

_STATUS_COUNTERS = {
    PredictionStatus.CONFIRMED: "confirmed_count",
    PredictionStatus.REFUTED: "refuted_count",
    PredictionStatus.PENDING: "pending_count",
    PredictionStatus.STRESSED: "stressed_count",
    PredictionStatus.NOT_YET_TESTABLE: "not_yet_testable_count",
    PredictionStatus.SUPERSEDED: "superseded_count",
}


def evidence_summary(
    graph: EpistemicGraphPort,
    hid: HypothesisId,
) -> EvidenceSummary:
    """Assemble a complete evidence picture for a hypothesis.

    Composes existing graph queries into a single read model that shows
    what predictions exist, how they stand, what assumptions underpin
    them, and whether linked analyses are fresh.

    Args:
        graph: The epistemic graph to query.
        hid: The hypothesis to summarise.

    Returns:
        EvidenceSummary: The assembled evidence picture.

    Raises:
        KeyError: If the hypothesis does not exist in the graph.
    """
    hypothesis = graph.get_hypothesis(hid)
    if hypothesis is None:
        raise KeyError(hid)

    # ── Predictions ───────────────────────────────────────────────
    prediction_ids = graph.predictions_depending_on_hypothesis(hid)
    prediction_details: list[PredictionDetail] = []
    status_counts: dict[str, int] = {}

    for pid in sorted(prediction_ids):
        pred = graph.get_prediction(pid)
        if pred is None:
            continue  # defensive

        obs_details: list[ObservationDetail] = []
        for oid in sorted(pred.observations):
            obs = graph.observations.get(oid)
            if obs is not None:
                obs_details.append(
                    ObservationDetail(
                        id=obs.id,
                        description=obs.description,
                        status=obs.status,
                    )
                )

        prediction_details.append(
            PredictionDetail(
                id=pred.id,
                observable=pred.observable,
                status=pred.status,
                tier=pred.tier,
                evidence_kind=pred.evidence_kind,
                predicted=pred.predicted,
                observed=pred.observed,
                observations=obs_details,
            )
        )

        counter = _STATUS_COUNTERS.get(pred.status)
        if counter:
            status_counts[counter] = status_counts.get(counter, 0) + 1

    # ── Assumptions ───────────────────────────────────────────────
    direct_aids = hypothesis.assumptions
    all_aids = graph.assumption_lineage(hid)

    assumption_details: list[AssumptionDetail] = []
    for aid in sorted(all_aids):
        assumption = graph.get_assumption(aid)
        if assumption is None:
            continue
        assumption_details.append(
            AssumptionDetail(
                id=assumption.id,
                statement=assumption.statement,
                criticality=assumption.criticality,
                tested_by=sorted(assumption.tested_by),
                direct=aid in direct_aids,
            )
        )

    # ── Analyses ──────────────────────────────────────────────────
    analysis_details: list[AnalysisDetail] = []
    for anid in sorted(hypothesis.analyses):
        analysis = graph.analyses.get(anid)
        if analysis is None:
            continue
        stale = False
        for par_id in analysis.uses_parameters:
            param = graph.parameters.get(par_id)
            if param is None:
                continue
            if param.last_modified is not None and (
                analysis.last_result_date is None
                or param.last_modified > analysis.last_result_date
            ):
                stale = True
                break
        analysis_details.append(
            AnalysisDetail(
                id=analysis.id,
                has_result=analysis.last_result is not None,
                stale=stale,
            )
        )

    # ── Objectives ────────────────────────────────────────────────
    objective_details: list[ObjectiveDetail] = []
    for tid in sorted(hypothesis.objectives):
        objective = graph.objectives.get(tid)
        if objective is not None:
            objective_details.append(
                ObjectiveDetail(id=objective.id, title=objective.title, kind=objective.kind, status=objective.status)
            )

    return EvidenceSummary(
        hypothesis_id=hid,
        hypothesis_statement=hypothesis.statement,
        hypothesis_status=hypothesis.status,
        predictions=prediction_details,
        assumptions=assumption_details,
        analyses=analysis_details,
        objectives=objective_details,
        **status_counts,
    )
