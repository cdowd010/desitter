"""Client helper implementations for core hypothesis resources."""
from __future__ import annotations

from datetime import date
from typing import Iterable, Mapping

from ._types import ClientResult
from ..epistemic.model import Analysis, Assumption, Experiment, Hypothesis, Observation, Prediction
from ..epistemic.types import (
    AssumptionType,
    ExperimentStatus,
    HypothesisCategory,
    HypothesisStatus,
    HypothesisType,
    ConfidenceTier,
    EvidenceKind,
    MeasurementRegime,
    ObservationStatus,
    PredictionStatus,
)


class _EpistemeClientHypothesisHelpers:
    """Typed helpers for hypotheses, assumptions, predictions, analyses, and observations."""

    # ── Hypothesis ────────────────────────────────────────────────

    def register_hypothesis(
        self,
        id: str,
        statement: str,
        *,
        type: HypothesisType | str = HypothesisType.DERIVED,
        scope: str = "global",
        refutation_criteria: str | None = None,
        dry_run: bool = False,
        status: HypothesisStatus | str | None = None,
        category: HypothesisCategory | str | None = None,
        assumptions: Iterable[str] | None = None,
        objectives: Iterable[str] | None = None,
        depends_on: Iterable[str] | None = None,
        analyses: Iterable[str] | None = None,
        parameter_constraints: Mapping[str, str] | None = None,
        source: str | None = None,
    ) -> ClientResult[Hypothesis]:
        type_str = type.value if isinstance(type, HypothesisType) else type
        status_str = status.value if isinstance(status, HypothesisStatus) else status
        category_str = category.value if isinstance(category, HypothesisCategory) else category
        return self.register(
            "hypothesis",
            dry_run=dry_run,
            id=id,
            statement=statement,
            type=type_str,
            scope=scope,
            refutation_criteria=refutation_criteria,
            status=status_str,
            category=category_str,
            assumptions=list(assumptions) if assumptions is not None else None,
            objectives=list(objectives) if objectives is not None else None,
            depends_on=list(depends_on) if depends_on is not None else None,
            analyses=list(analyses) if analyses is not None else None,
            parameter_constraints=dict(parameter_constraints) if parameter_constraints is not None else None,
            source=source,
        )

    def get_hypothesis(self, identifier: str) -> ClientResult[Hypothesis]:
        return self.get("hypothesis", identifier)

    def list_hypotheses(self, **filters: object) -> ClientResult[list[Hypothesis]]:
        return self.list("hypothesis", **filters)

    def set_hypothesis(
        self, identifier: str, *, dry_run: bool = False, **payload: object
    ) -> ClientResult[Hypothesis]:
        return self.set("hypothesis", identifier, dry_run=dry_run, **payload)

    def transition_hypothesis(
        self,
        identifier: str,
        new_status: HypothesisStatus | str,
        *,
        dry_run: bool = False,
    ) -> ClientResult[Hypothesis]:
        return self.transition("hypothesis", identifier, new_status, dry_run=dry_run)

    # ── Assumption ────────────────────────────────────────────────

    def register_assumption(
        self,
        id: str,
        statement: str,
        type: AssumptionType | str = AssumptionType.EMPIRICAL,
        *,
        scope: str = "global",
        dry_run: bool = False,
        criticality: object | None = None,
        depends_on: Iterable[str] | None = None,
        falsifiable_consequence: str | None = None,
        source: str | None = None,
        notes: str | None = None,
    ) -> ClientResult[Assumption]:
        type_str = type.value if isinstance(type, AssumptionType) else type
        criticality_str = criticality.value if hasattr(criticality, "value") else criticality
        return self.register(
            "assumption",
            dry_run=dry_run,
            id=id,
            statement=statement,
            type=type_str,
            scope=scope,
            criticality=criticality_str,
            depends_on=list(depends_on) if depends_on is not None else None,
            falsifiable_consequence=falsifiable_consequence,
            source=source,
            notes=notes,
        )

    def get_assumption(self, identifier: str) -> ClientResult[Assumption]:
        return self.get("assumption", identifier)

    def list_assumptions(self, **filters: object) -> ClientResult[list[Assumption]]:
        return self.list("assumption", **filters)

    def set_assumption(
        self, identifier: str, *, dry_run: bool = False, **payload: object
    ) -> ClientResult[Assumption]:
        return self.set("assumption", identifier, dry_run=dry_run, **payload)

    # ── Prediction ────────────────────────────────────────────────

    def register_prediction(
        self,
        id: str,
        observable: str,
        predicted: object,
        *,
        tier: ConfidenceTier | str = ConfidenceTier.FULLY_SPECIFIED,
        status: PredictionStatus | str = PredictionStatus.PENDING,
        evidence_kind: EvidenceKind | str = EvidenceKind.NOVEL_PREDICTION,
        measurement_regime: MeasurementRegime | str = MeasurementRegime.MEASURED,
        dry_run: bool = False,
        specification: str | None = None,
        derivation: str | None = None,
        hypothesis_ids: Iterable[str] | None = None,
        tests_assumptions: Iterable[str] | None = None,
        analysis: str | None = None,
        independence_group: str | None = None,
        correlation_tags: Iterable[str] | None = None,
        observed: object | None = None,
        observed_bound: object | None = None,
        free_params: int | None = None,
        conditional_on: Iterable[str] | None = None,
        refutation_criteria: str | None = None,
        stress_criteria: str | None = None,
        benchmark_source: str | None = None,
        source: str | None = None,
        notes: str | None = None,
    ) -> ClientResult[Prediction]:
        tier_str = tier.value if isinstance(tier, ConfidenceTier) else tier
        status_str = status.value if isinstance(status, PredictionStatus) else status
        ek_str = evidence_kind.value if isinstance(evidence_kind, EvidenceKind) else evidence_kind
        mr_str = measurement_regime.value if isinstance(measurement_regime, MeasurementRegime) else measurement_regime
        return self.register(
            "prediction",
            dry_run=dry_run,
            id=id,
            observable=observable,
            predicted=predicted,
            tier=tier_str,
            status=status_str,
            evidence_kind=ek_str,
            measurement_regime=mr_str,
            specification=specification,
            derivation=derivation,
            hypothesis_ids=list(hypothesis_ids) if hypothesis_ids is not None else None,
            tests_assumptions=list(tests_assumptions) if tests_assumptions is not None else None,
            analysis=analysis,
            independence_group=independence_group,
            correlation_tags=list(correlation_tags) if correlation_tags is not None else None,
            observed=observed,
            observed_bound=observed_bound,
            free_params=free_params,
            conditional_on=list(conditional_on) if conditional_on is not None else None,
            refutation_criteria=refutation_criteria,
            stress_criteria=stress_criteria,
            benchmark_source=benchmark_source,
            source=source,
            notes=notes,
        )

    def get_prediction(self, identifier: str) -> ClientResult[Prediction]:
        return self.get("prediction", identifier)

    def list_predictions(self, **filters: object) -> ClientResult[list[Prediction]]:
        return self.list("prediction", **filters)

    def set_prediction(
        self, identifier: str, *, dry_run: bool = False, **payload: object
    ) -> ClientResult[Prediction]:
        return self.set("prediction", identifier, dry_run=dry_run, **payload)

    def transition_prediction(
        self,
        identifier: str,
        new_status: PredictionStatus | str,
        *,
        dry_run: bool = False,
    ) -> ClientResult[Prediction]:
        return self.transition("prediction", identifier, new_status, dry_run=dry_run)

    # ── Analysis ──────────────────────────────────────────────────

    def register_analysis(
        self,
        id: str,
        *,
        dry_run: bool = False,
        command: str | None = None,
        path: str | None = None,
        uses_parameters: Iterable[str] | None = None,
        notes: str | None = None,
        last_result: object | None = None,
        last_result_sha: str | None = None,
        last_result_date: date | str | None = None,
    ) -> ClientResult[Analysis]:
        date_str = (
            last_result_date.isoformat()
            if hasattr(last_result_date, "isoformat")
            else last_result_date
        )
        return self.register(
            "analysis",
            dry_run=dry_run,
            id=id,
            command=command,
            path=path,
            uses_parameters=list(uses_parameters) if uses_parameters is not None else None,
            notes=notes,
            last_result=last_result,
            last_result_sha=last_result_sha,
            last_result_date=date_str,
        )

    def get_analysis(self, identifier: str) -> ClientResult[Analysis]:
        return self.get("analysis", identifier)

    def list_analyses(self, **filters: object) -> ClientResult[list[Analysis]]:
        return self.list("analysis", **filters)

    def set_analysis(
        self, identifier: str, *, dry_run: bool = False, **payload: object
    ) -> ClientResult[Analysis]:
        return self.set("analysis", identifier, dry_run=dry_run, **payload)

    # ── Observation ───────────────────────────────────────────────

    def register_observation(
        self,
        id: str,
        description: str,
        value: object,
        date: date | str,
        *,
        status: ObservationStatus | str = ObservationStatus.PRELIMINARY,
        dry_run: bool = False,
        predictions: Iterable[str] | None = None,
        source: str | None = None,
        notes: str | None = None,
    ) -> ClientResult[Observation]:
        status_str = status.value if isinstance(status, ObservationStatus) else status
        date_str = date.isoformat() if hasattr(date, "isoformat") else date
        return self.register(
            "observation",
            dry_run=dry_run,
            id=id,
            description=description,
            value=value,
            date=date_str,
            status=status_str,
            predictions=list(predictions) if predictions is not None else None,
            source=source,
            notes=notes,
        )

    def get_observation(self, identifier: str) -> ClientResult[Observation]:
        return self.get("observation", identifier)

    def list_observations(self, **filters: object) -> ClientResult[list[Observation]]:
        return self.list("observation", **filters)

    def set_observation(
        self, identifier: str, *, dry_run: bool = False, **payload: object
    ) -> ClientResult[Observation]:
        return self.set("observation", identifier, dry_run=dry_run, **payload)

    def transition_observation(
        self,
        identifier: str,
        new_status: ObservationStatus | str,
        *,
        dry_run: bool = False,
    ) -> ClientResult[Observation]:
        return self.transition("observation", identifier, new_status, dry_run=dry_run)

    # ── Experiment ────────────────────────────────────────────────

    def register_experiment(
        self,
        id: str,
        title: str,
        *,
        dry_run: bool = False,
        status: ExperimentStatus | str | None = None,
        protocol: str | None = None,
        predictions_tested: Iterable[str] | None = None,
        assumptions_tested: Iterable[str] | None = None,
        replicate_of: str | None = None,
        instrument: str | None = None,
        conditions: str | None = None,
        date: date | str | None = None,
        source: str | None = None,
        notes: str | None = None,
        tags: Iterable[str] | None = None,
    ) -> ClientResult[Experiment]:
        status_str = status.value if isinstance(status, ExperimentStatus) else status
        date_str = date.isoformat() if hasattr(date, "isoformat") else date
        return self.register(
            "experiment",
            dry_run=dry_run,
            id=id,
            title=title,
            status=status_str,
            protocol=protocol,
            predictions_tested=list(predictions_tested) if predictions_tested is not None else None,
            assumptions_tested=list(assumptions_tested) if assumptions_tested is not None else None,
            replicate_of=replicate_of,
            instrument=instrument,
            conditions=conditions,
            date=date_str,
            source=source,
            notes=notes,
            tags=list(tags) if tags is not None else None,
        )

    def get_experiment(self, identifier: str) -> ClientResult[Experiment]:
        return self.get("experiment", identifier)

    def list_experiments(self, **filters: object) -> ClientResult[list[Experiment]]:
        return self.list("experiment", **filters)

    def set_experiment(
        self, identifier: str, *, dry_run: bool = False, **payload: object
    ) -> ClientResult[Experiment]:
        return self.set("experiment", identifier, dry_run=dry_run, **payload)

    def transition_experiment(
        self,
        identifier: str,
        new_status: ExperimentStatus | str,
        *,
        dry_run: bool = False,
    ) -> ClientResult[Experiment]:
        return self.transition("experiment", identifier, new_status, dry_run=dry_run)


__all__ = ["_EpistemeClientHypothesisHelpers"]

