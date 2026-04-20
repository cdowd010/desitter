"""Shared pytest fixtures for the Episteme test suite."""
from __future__ import annotations

from datetime import date

import pytest

from episteme.epistemic.graph import EpistemicGraph
from episteme.epistemic.model import (
    Analysis,
    AnalysisId,
    Assumption,
    AssumptionId,
    AssumptionType,
    Hypothesis,
    HypothesisId,
    HypothesisType,
    Observation,
    ObservationId,
    ObservationStatus,
    Parameter,
    ParameterId,
    Prediction,
    PredictionId,
    PredictionStatus,
    Objective,
    ObjectiveId,
    ObjectiveKind,
    ObjectiveStatus,
)
from episteme.epistemic.types import (
    Criticality,
    ConfidenceTier,
    EvidenceKind,
    MeasurementRegime,
)


@pytest.fixture
def base_graph() -> EpistemicGraph:
    """EpistemicGraph populated with the standard set of test entities.

    Entity graph:
        Objective T-001  ←→  Hypothesis C-001  →  Assumption A-001 (LOAD_BEARING)
                              ↓
                         Prediction P-001 (stress_criteria set)
                              ↑
                         Observation OBS-002 (VALIDATED)
        Observation OBS-001 (standalone, PRELIMINARY)
        Parameter PAR-001 (last_modified=2026-04-10)
        Analysis AN-001   (last_result_date=2026-04-05)  ← stale
    """
    graph = EpistemicGraph()

    graph = graph.register_objective(
        Objective(id=ObjectiveId("T-001"), title="Catalysis Objective", kind=ObjectiveKind.EXPLANATORY, status=ObjectiveStatus.ACTIVE)
    )

    graph = graph.register_assumption(
        Assumption(
            id=AssumptionId("A-001"),
            statement="Detector calibrated",
            type=AssumptionType.EMPIRICAL,
            scope="global",
            criticality=Criticality.LOAD_BEARING,
        )
    )

    graph = graph.register_hypothesis(
        Hypothesis(
            id=HypothesisId("C-001"),
            statement="Catalyst X increases yield",
            type=HypothesisType.FOUNDATIONAL,
            scope="global",
            refutation_criteria="Show yield does not increase",
            assumptions={AssumptionId("A-001")},
            objectives={ObjectiveId("T-001")},
        )
    )

    graph = graph.register_prediction(
        Prediction(
            id=PredictionId("P-001"),
            observable="yield",
            tier=ConfidenceTier.FULLY_SPECIFIED,
            status=PredictionStatus.PENDING,
            evidence_kind=EvidenceKind.NOVEL_PREDICTION,
            measurement_regime=MeasurementRegime.MEASURED,
            predicted=0.15,
            hypothesis_ids={HypothesisId("C-001")},
            stress_criteria="Yield increase <10% but >5% would be stressed",
        )
    )

    graph = graph.register_observation(
        Observation(
            id=ObservationId("OBS-001"),
            description="Initial yield measurement",
            value=12.5,
            date=date(2026, 4, 1),
            status=ObservationStatus.PRELIMINARY,
        )
    )

    graph = graph.register_observation(
        Observation(
            id=ObservationId("OBS-002"),
            description="Controlled experiment result",
            value=14.8,
            date=date(2026, 4, 15),
            status=ObservationStatus.VALIDATED,
            predictions={PredictionId("P-001")},
        )
    )

    graph = graph.register_parameter(
        Parameter(
            id=ParameterId("PAR-001"),
            name="threshold",
            value=0.85,
            last_modified=date(2026, 4, 10),
        )
    )

    graph = graph.register_analysis(
        Analysis(id=AnalysisId("AN-001"), uses_parameters={ParameterId("PAR-001")})
    )

    graph = graph.record_analysis_result(
        AnalysisId("AN-001"), result=42, result_date=date(2026, 4, 5)
    )

    return graph
