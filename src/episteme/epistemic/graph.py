"""The EpistemicGraph: aggregate root for the epistemic domain.

External code NEVER modifies entities directly — it calls methods on the
graph, and the graph ensures consistency.

Every mutation method returns a NEW graph. This gives free undo/redo and
eliminates state corruption.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import date

from .model import (
    Analysis,
    Assumption,
    Hypothesis,
    DeadEnd,
    Discovery,
    IndependenceGroup,
    Observation,
    PairwiseSeparation,
    Parameter,
    Prediction,
    Objective,
)
from .errors import (
    BrokenReferenceError,
    CycleError,
    DuplicateIdError,
    EpistemicError,
    InvariantViolation,
)
from .types import (
    AnalysisId,
    AssumptionId,
    HypothesisId,
    HypothesisStatus,
    DeadEndId,
    DeadEndStatus,
    DiscoveryId,
    DiscoveryStatus,
    IndependenceGroupId,
    ObservationId,
    ObservationStatus,
    ParameterId,
    PairwiseSeparationId,
    PredictionId,
    PredictionStatus,
    ObjectiveId,
    ObjectiveStatus,
)


@dataclass
class EpistemicGraph:
    """Complete epistemic state of a research project.

    The EpistemicGraph is the aggregate root for the epistemic domain.
    External code NEVER modifies entities directly — it calls methods
    on the graph, and the graph ensures consistency.

    Every mutation method returns a NEW graph instance. The old graph is
    left untouched, providing free rollback/undo semantics and
    eliminating state corruption from partial mutations.

    All bidirectional links between entities (e.g.
    ``Assumption.used_in_hypotheses`` ↔ ``Hypothesis.assumptions``,
    ``Parameter.used_in_analyses`` ↔ ``Analysis.uses_parameters``)
    are maintained automatically by the graph's register/update/remove
    methods.

    Attributes:
        hypotheses: Registry of all hypotheses, keyed by ``HypothesisId``.
        assumptions: Registry of all assumptions, keyed by ``AssumptionId``.
        predictions: Registry of all predictions, keyed by ``PredictionId``.
        objectives: Registry of all objectives, keyed by ``ObjectiveId``.
        discoveries: Registry of all discoveries, keyed by ``DiscoveryId``.
        analyses: Registry of all analyses, keyed by ``AnalysisId``.
        independence_groups: Registry of all independence groups, keyed
            by ``IndependenceGroupId``.
        pairwise_separations: Registry of all pairwise separation records,
            keyed by ``PairwiseSeparationId``.
        dead_ends: Registry of all dead end records, keyed by ``DeadEndId``.
        parameters: Registry of all parameters, keyed by ``ParameterId``.
        observations: Registry of all observations, keyed by ``ObservationId``.
        version: Monotonically increasing integer, incremented by the
            repository on each successful save. Zero for in-memory webs.
            Used for optimistic concurrency control when multiple sessions
            share the same backing store.
    """
    version: int = 0
    hypotheses: dict[HypothesisId, Hypothesis] = field(default_factory=dict)
    assumptions: dict[AssumptionId, Assumption] = field(default_factory=dict)
    predictions: dict[PredictionId, Prediction] = field(default_factory=dict)
    objectives: dict[ObjectiveId, Objective] = field(default_factory=dict)
    discoveries: dict[DiscoveryId, Discovery] = field(default_factory=dict)
    analyses: dict[AnalysisId, Analysis] = field(default_factory=dict)
    independence_groups: dict[IndependenceGroupId, IndependenceGroup] = field(
        default_factory=dict
    )
    pairwise_separations: dict[PairwiseSeparationId, PairwiseSeparation] = field(default_factory=dict)
    dead_ends: dict[DeadEndId, DeadEnd] = field(default_factory=dict)
    parameters: dict[ParameterId, Parameter] = field(default_factory=dict)
    observations: dict[ObservationId, Observation] = field(default_factory=dict)

    # ── Queries ───────────────────────────────────────────────────

    def get_hypothesis(self, cid: HypothesisId) -> Hypothesis | None:
        """Return a hypothesis by ID, or ``None`` when the hypothesis does not exist.

        Args:
            cid: The unique identifier of the hypothesis to look up.

        Returns:
            Hypothesis | None: The hypothesis instance, or ``None`` if not found.
        """
        return self.hypotheses.get(cid)

    def get_assumption(self, aid: AssumptionId) -> Assumption | None:
        """Return an assumption by ID, or ``None`` when absent from the graph.

        Args:
            aid: The unique identifier of the assumption to look up.

        Returns:
            Assumption | None: The assumption instance, or ``None`` if
                not found.
        """
        return self.assumptions.get(aid)

    def get_prediction(self, pid: PredictionId) -> Prediction | None:
        """Return a prediction by ID, or ``None`` when no match exists.

        Args:
            pid: The unique identifier of the prediction to look up.

        Returns:
            Prediction | None: The prediction instance, or ``None`` if
                not found.
        """
        return self.predictions.get(pid)

    def hypotheses_using_assumption(self, aid: AssumptionId) -> set[HypothesisId]:
        """Return all hypotheses that reference this assumption in their assumptions set.

        Performs a full scan of all hypotheses. The returned set contains only
        direct references, not transitive ones.

        Args:
            aid: The assumption ID to search for.

        Returns:
            set[HypothesisId]: IDs of all hypotheses whose ``assumptions`` field
                contains ``aid``.
        """
        return {cid for cid, c in self.hypotheses.items() if aid in c.assumptions}

    def hypothesis_lineage(self, cid: HypothesisId) -> set[HypothesisId]:
        """Compute the transitive closure of a hypothesis's ``depends_on`` chain.

        Returns all ancestor hypotheses reachable through the ``depends_on``
        DAG. The input hypothesis itself is NOT included in the result.
        Uses an iterative depth-first traversal.

        Args:
            cid: The hypothesis ID whose ancestors to compute.

        Returns:
            set[HypothesisId]: All ancestor hypothesis IDs (transitive ``depends_on``
                closure), excluding ``cid`` itself.
        """
        visited: set[HypothesisId] = set()
        stack = [cid]
        while stack:
            current = stack.pop()
            hypothesis = self.hypotheses.get(current)
            if hypothesis is None:
                continue
            for dep in hypothesis.depends_on:
                if dep not in visited:
                    visited.add(dep)
                    stack.append(dep)
        return visited

    def assumption_lineage(self, cid: HypothesisId) -> set[AssumptionId]:
        """Return all assumptions reachable through a hypothesis and its ancestors.

        Collects assumptions from the hypothesis and all its transitive
        ancestors (via ``depends_on``), then expands through assumption
        ``depends_on`` chains to capture presupposed assumptions.

        Args:
            cid: The hypothesis ID whose full assumption lineage to compute.

        Returns:
            set[AssumptionId]: All assumption IDs transitively reachable
                through hypothesis and assumption dependency chains.
        """
        all_hypotheses = self.hypothesis_lineage(cid) | {cid}
        direct: set[AssumptionId] = set()
        for ancestor_id in all_hypotheses:
            hypothesis = self.hypotheses.get(ancestor_id)
            if hypothesis:
                direct.update(hypothesis.assumptions)
        # Expand through assumption.depends_on chains
        result: set[AssumptionId] = set()
        stack = list(direct)
        while stack:
            aid = stack.pop()
            if aid in result:
                continue
            result.add(aid)
            assumption = self.assumptions.get(aid)
            if assumption:
                for dep in assumption.depends_on:
                    if dep not in result:
                        stack.append(dep)
        return result

    def prediction_implicit_assumptions(self, pid: PredictionId) -> set[AssumptionId]:
        """Return all assumptions in the full derivation chain of a prediction.

        Computes the complete set of assumptions the prediction silently
        rests on by combining:

        1. Assumptions from each hypothesis in ``hypothesis_ids`` and their ancestors
           (via ``assumption_lineage``).
        2. Assumptions presupposed by those assumptions (``depends_on``
           chains).
        3. Assumptions in ``conditional_on`` and their ``depends_on`` chains.

        Args:
            pid: The prediction ID whose implicit assumptions to compute.

        Returns:
            set[AssumptionId]: The complete set of assumption IDs the
                prediction depends on. Empty set if the prediction does
                not exist.
        """
        pred = self.predictions.get(pid)
        if pred is None:
            return set()
        result: set[AssumptionId] = set()
        for cid in pred.hypothesis_ids:
            result.update(self.assumption_lineage(cid))
        # Expand conditional_on through depends_on chains
        stack = list(pred.conditional_on)
        while stack:
            aid = stack.pop()
            if aid in result:
                continue
            result.add(aid)
            assumption = self.assumptions.get(aid)
            if assumption:
                for dep in assumption.depends_on:
                    if dep not in result:
                        stack.append(dep)
        return result

    def refutation_impact(self, pid: PredictionId) -> dict[str, set]:
        """Compute the blast radius when a prediction is refuted.

        Answers "what is called into question when this prediction fails?"
        by tracing backward through the derivation chain.

        Args:
            pid: The prediction ID to analyze.

        Returns:
            dict[str, set]: A dictionary with three keys:

            - ``hypothesis_ids``: Direct hypotheses jointly implying this prediction
              (copy of ``Prediction.hypothesis_ids``).
            - ``hypothesis_ancestors``: All ancestor hypotheses via transitive
              ``depends_on`` closure, EXCLUDING the direct ``hypothesis_ids``.
            - ``implicit_assumptions``: All assumptions in the full
              derivation chain (same as ``prediction_implicit_assumptions``).

            Returns empty sets for all keys if the prediction does not exist.
        """
        pred = self.predictions.get(pid)
        if pred is None:
            return {"hypothesis_ids": set(), "hypothesis_ancestors": set(), "implicit_assumptions": set()}
        ancestors: set[HypothesisId] = set()
        for cid in pred.hypothesis_ids:
            ancestors.update(self.hypothesis_lineage(cid))
        return {
            "hypothesis_ids": pred.hypothesis_ids.copy(),
            "hypothesis_ancestors": ancestors - pred.hypothesis_ids,
            "implicit_assumptions": self.prediction_implicit_assumptions(pid),
        }

    def assumption_support_status(self, aid: AssumptionId) -> dict[str, set]:
        """Compute the full dependency and test coverage of an assumption.

        Answers "what depends on this assumption, and what tests it?"

        Args:
            aid: The assumption ID to analyze.

        Returns:
            dict[str, set]: A dictionary with three keys:

            - ``direct_hypotheses``: Claims that directly reference this
              assumption in their ``assumptions`` set.
            - ``dependent_predictions``: Predictions whose full derivation
              chain includes this assumption (via implicit assumptions).
            - ``tested_by``: Predictions explicitly testing this assumption
              (via ``tests_assumptions``).

            Returns empty sets for all keys if the assumption does not exist.
        """
        assumption = self.assumptions.get(aid)
        if assumption is None:
            return {"direct_hypotheses": set(), "dependent_predictions": set(), "tested_by": set()}
        # Build inverse index once: {AssumptionId: set[PredictionId]}
        implicit_dependents: dict[AssumptionId, set[PredictionId]] = {}
        for pid in self.predictions:
            for dep_aid in self.prediction_implicit_assumptions(pid):
                implicit_dependents.setdefault(dep_aid, set()).add(pid)
        dependent = implicit_dependents.get(aid, set())
        return {
            "direct_hypotheses": assumption.used_in_hypotheses.copy(),
            "dependent_predictions": dependent,
            "tested_by": assumption.tested_by.copy(),
        }

    def hypotheses_depending_on_hypothesis(self, cid: HypothesisId) -> set[HypothesisId]:
        """Return all hypotheses that transitively depend on this hypothesis.

        Performs a forward traversal from ``cid`` using a reverse
        ``depends_on`` index: "if this hypothesis is wrong, which downstream
        hypotheses are built on it?" The input hypothesis itself is NOT included.

        Args:
            cid: The hypothesis ID to trace forward from.

        Returns:
            set[HypothesisId]: All downstream hypothesis IDs that directly or
                transitively depend on ``cid``.
        """
        reverse: dict[HypothesisId, set[HypothesisId]] = {}
        for other_id, hypothesis in self.hypotheses.items():
            for dep in hypothesis.depends_on:
                reverse.setdefault(dep, set()).add(other_id)
        result: set[HypothesisId] = set()
        stack = list(reverse.get(cid, set()))
        while stack:
            current = stack.pop()
            if current in result:
                continue
            result.add(current)
            stack.extend(reverse.get(current, set()))
        return result

    def predictions_depending_on_hypothesis(self, cid: HypothesisId) -> set[PredictionId]:
        """Return all predictions whose derivation chain includes this hypothesis.

        Answers "if this hypothesis is retracted, which predictions are now
        suspect?" Considers both direct and downstream hypothesis dependencies.

        Args:
            cid: The hypothesis ID to trace forward from.

        Returns:
            set[PredictionId]: All prediction IDs whose ``hypothesis_ids``
                intersect with ``cid`` or any of its downstream dependents.
        """
        affected_hypotheses = self.hypotheses_depending_on_hypothesis(cid) | {cid}
        return {
            pid for pid, pred in self.predictions.items()
            if pred.hypothesis_ids & affected_hypotheses
        }

    def parameter_impact(self, pid: ParameterId) -> dict[str, set]:
        """Compute the full blast radius of a parameter change.

        Walks the dependency chain: parameter → stale analyses → hypotheses
        covered by those analyses → predictions depending on those hypotheses.
        Also includes hypotheses with ``parameter_constraints`` annotations
        for this parameter and predictions directly linked to stale analyses.

        Args:
            pid: The parameter ID whose impact to compute.

        Returns:
            dict[str, set]: A dictionary with four keys:

            - ``stale_analyses``: Analysis IDs that use this parameter.
            - ``constrained_hypotheses``: Hypothesis IDs with a threshold annotation
              on this parameter.
            - ``affected_hypotheses``: Union of hypotheses covered by stale analyses
              and constrained hypotheses.
            - ``affected_predictions``: All predictions in the downstream
              chain of affected hypotheses, plus predictions directly linked
              to stale analyses.

            Returns empty sets for all keys if the parameter does not exist.
        """
        param = self.parameters.get(pid)
        if param is None:
            return {
                "stale_analyses": set(), "constrained_hypotheses": set(),
                "affected_hypotheses": set(), "affected_predictions": set(),
            }
        stale_analyses = param.used_in_analyses.copy()
        # Claims covered by stale analyses
        affected_hypotheses: set[HypothesisId] = set()
        for anid in stale_analyses:
            analysis = self.analyses.get(anid)
            if analysis:
                affected_hypotheses.update(analysis.hypotheses_covered)
        # Claims with explicit threshold constraints on this parameter
        constrained_hypotheses = {
            cid for cid, c in self.hypotheses.items()
            if pid in c.parameter_constraints
        }
        affected_hypotheses.update(constrained_hypotheses)
        # Predictions depending on affected hypotheses (direct + downstream)
        affected_predictions: set[PredictionId] = set()
        for cid in affected_hypotheses:
            affected_predictions.update(self.predictions_depending_on_hypothesis(cid))
        # Also predictions directly linked to stale analyses
        for pred_id, pred in self.predictions.items():
            if pred.analysis in stale_analyses:
                affected_predictions.add(pred_id)
        return {
            "stale_analyses": stale_analyses,
            "constrained_hypotheses": constrained_hypotheses,
            "affected_hypotheses": affected_hypotheses,
            "affected_predictions": affected_predictions,
        }

    # ── Mutations (return new graph) ────────────────────────────────

    def register_hypothesis(self, hypothesis: Hypothesis) -> EpistemicGraph:
        """Register a new hypothesis in the graph.

        Enforces: no duplicate IDs, all referenced assumptions/hypotheses/analyses/
        parameters exist, no dependency cycles in ``depends_on``, and
        bidirectional backlinks are updated on assumptions and analyses.

        The incoming entity is deep-copied so the caller's reference cannot
        mutate the graph's stored copy after registration.

        Args:
            hypothesis: The hypothesis to register. Must have a unique ``id``.

        Returns:
            EpistemicGraph: A new graph instance containing the registered hypothesis.

        Raises:
            DuplicateIdError: If ``hypothesis.id`` already exists.
            BrokenReferenceError: If any referenced ID does not exist.
            CycleError: If ``depends_on`` would create a dependency cycle.
        """
        if hypothesis.id in self.hypotheses:
            raise DuplicateIdError(f"Hypothesis {hypothesis.id} already exists")
        self._check_refs_exist(hypothesis.assumptions, self.assumptions, "assumption")
        self._check_refs_exist(hypothesis.depends_on, self.hypotheses, "hypothesis")
        self._check_refs_exist(hypothesis.analyses, self.analyses, "analysis")
        self._check_refs_exist(set(hypothesis.parameter_constraints.keys()), self.parameters, "parameter")
        self._check_refs_exist(hypothesis.objectives, self.objectives, "objective")
        self._check_no_cycle_with(hypothesis)

        new = self._copy()
        # Deep-copy the incoming entity so a caller who keeps a reference
        # cannot mutate the graph's stored copy after registration. All
        # register_* methods follow this same pattern.
        new.hypotheses[hypothesis.id] = copy.deepcopy(hypothesis)

        # Maintain bidirectional: assumption.used_in_hypotheses
        for aid in hypothesis.assumptions:
            new.assumptions[aid] = copy.deepcopy(new.assumptions[aid])
            new.assumptions[aid].used_in_hypotheses.add(hypothesis.id)

        # Maintain bidirectional: analysis.hypotheses_covered
        for anid in hypothesis.analyses:
            new.analyses[anid] = copy.deepcopy(new.analyses[anid])
            new.analyses[anid].hypotheses_covered.add(hypothesis.id)

        # Maintain bidirectional: objective.motivates_hypotheses
        for tid in hypothesis.objectives:
            new.objectives[tid] = copy.deepcopy(new.objectives[tid])
            new.objectives[tid].motivates_hypotheses.add(hypothesis.id)

        return new

    def register_assumption(self, assumption: Assumption) -> EpistemicGraph:
        """Register a new assumption in the graph.

        Validates that all ``depends_on`` references exist and that no
        cycle would be introduced. Backlinks ``used_in_hypotheses`` and
        ``tested_by`` are intentionally initialized to empty sets —
        they are owned by hypothesis and prediction operations respectively.

        Args:
            assumption: The assumption to register. Must have a unique ``id``.

        Returns:
            EpistemicGraph: A new graph instance containing the registered assumption.

        Raises:
            DuplicateIdError: If ``assumption.id`` already exists.
            BrokenReferenceError: If any ``depends_on`` ID does not exist.
            CycleError: If ``depends_on`` would create a cycle.
        """
        if assumption.id in self.assumptions:
            raise DuplicateIdError(f"Assumption {assumption.id} already exists")
        self._check_refs_exist(assumption.depends_on, self.assumptions, "assumption")
        self._check_no_assumption_cycle_with(assumption)
        new = self._copy()
        stored = copy.deepcopy(assumption)
        stored.used_in_hypotheses = set()
        stored.tested_by = set()
        new.assumptions[assumption.id] = stored
        return new

    def register_prediction(self, prediction: Prediction) -> EpistemicGraph:
        """Register a new prediction in the graph.

        Validates that all referenced hypotheses, assumptions, analysis, and
        independence group exist. Updates bidirectional backlinks:
        ``Assumption.tested_by`` and ``IndependenceGroup.member_predictions``.

        Args:
            prediction: The prediction to register. Must have a unique ``id``.

        Returns:
            EpistemicGraph: A new graph instance containing the registered prediction.

        Raises:
            DuplicateIdError: If ``prediction.id`` already exists.
            BrokenReferenceError: If any referenced ID does not exist.
        """
        if prediction.id in self.predictions:
            raise DuplicateIdError(f"Prediction {prediction.id} already exists")
        self._check_refs_exist(prediction.hypothesis_ids, self.hypotheses, "hypothesis")
        self._check_refs_exist(prediction.tests_assumptions, self.assumptions, "assumption")
        self._check_refs_exist(prediction.conditional_on, self.assumptions, "assumption")
        if prediction.analysis and prediction.analysis not in self.analyses:
            raise BrokenReferenceError(
                f"Analysis {prediction.analysis} does not exist"
            )
        if prediction.independence_group:
            if prediction.independence_group not in self.independence_groups:
                raise BrokenReferenceError(
                    f"Independence group {prediction.independence_group} does not exist"
                )

        new = self._copy()
        new.predictions[prediction.id] = copy.deepcopy(prediction)

        # Maintain bidirectional: assumption.tested_by
        for aid in prediction.tests_assumptions:
            new.assumptions[aid] = copy.deepcopy(new.assumptions[aid])
            new.assumptions[aid].tested_by.add(prediction.id)

        # Maintain bidirectional: group.member_predictions
        if prediction.independence_group:
            gid = prediction.independence_group
            new.independence_groups[gid] = copy.deepcopy(new.independence_groups[gid])
            new.independence_groups[gid].member_predictions.add(prediction.id)

        return new

    def register_analysis(self, analysis: Analysis) -> EpistemicGraph:
        """Register a new analysis reference in the graph.

        Validates that all ``uses_parameters`` IDs exist and updates the
        bidirectional ``Parameter.used_in_analyses`` backlink.
        ``hypotheses_covered`` is a backlink owned by hypothesis operations and
        starts empty.

        Args:
            analysis: The analysis to register. Must have a unique ``id``.

        Returns:
            EpistemicGraph: A new graph instance containing the registered analysis.

        Raises:
            DuplicateIdError: If ``analysis.id`` already exists.
            BrokenReferenceError: If any ``uses_parameters`` ID does not exist.
        """
        if analysis.id in self.analyses:
            raise DuplicateIdError(f"Analysis {analysis.id} already exists")
        self._check_refs_exist(analysis.uses_parameters, self.parameters, "parameter")

        new = self._copy()
        stored = copy.deepcopy(analysis)
        stored.hypotheses_covered = set()
        new.analyses[analysis.id] = stored

        # Maintain bidirectional: parameter.used_in_analyses
        for pid in analysis.uses_parameters:
            new.parameters[pid] = copy.deepcopy(new.parameters[pid])
            new.parameters[pid].used_in_analyses.add(analysis.id)

        return new

    def register_objective(self, objective: Objective) -> EpistemicGraph:
        """Register a new objective in the graph.

        Validates that all ``related_predictions``, ``related_dead_ends``,
        and ``related_discoveries`` IDs exist.
        ``motivates_hypotheses`` is a backlink maintained by hypothesis
        operations and starts empty.

        Args:
            objective: The objective to register. Must have a unique ``id``.

        Returns:
            EpistemicGraph: A new graph instance containing the registered objective.

        Raises:
            DuplicateIdError: If ``objective.id`` already exists.
            BrokenReferenceError: If any referenced ID does not exist.
        """
        if objective.id in self.objectives:
            raise DuplicateIdError(f"Objective {objective.id} already exists")
        self._check_refs_exist(objective.related_predictions, self.predictions, "prediction")
        self._check_refs_exist(objective.related_dead_ends, self.dead_ends, "dead_end")
        self._check_refs_exist(objective.related_discoveries, self.discoveries, "discovery")
        new = self._copy()
        stored = copy.deepcopy(objective)
        stored.motivates_hypotheses = set()
        new.objectives[objective.id] = stored
        return new

    def register_independence_group(self, group: IndependenceGroup) -> EpistemicGraph:
        """Register a new independence group in the graph.

        Validates that all ``hypothesis_lineage`` and ``assumption_lineage`` IDs
        exist. ``member_predictions`` is a backlink owned by prediction
        operations and starts empty.

        Args:
            group: The independence group to register. Must have a unique ``id``.

        Returns:
            EpistemicGraph: A new graph instance containing the registered group.

        Raises:
            DuplicateIdError: If ``group.id`` already exists.
            BrokenReferenceError: If any lineage ID does not exist.
        """
        if group.id in self.independence_groups:
            raise DuplicateIdError(f"Independence group {group.id} already exists")
        self._check_refs_exist(group.hypothesis_lineage, self.hypotheses, "hypothesis")
        self._check_refs_exist(group.assumption_lineage, self.assumptions, "assumption")
        new = self._copy()
        stored = copy.deepcopy(group)
        stored.member_predictions = set()
        new.independence_groups[group.id] = stored
        return new

    def register_discovery(self, discovery: Discovery) -> EpistemicGraph:
        """Register a new discovery in the graph.

        Validates that all ``related_hypotheses`` and ``related_predictions``
        IDs exist.

        Args:
            discovery: The discovery to register. Must have a unique ``id``.

        Returns:
            EpistemicGraph: A new graph instance containing the registered discovery.

        Raises:
            DuplicateIdError: If ``discovery.id`` already exists.
            BrokenReferenceError: If any referenced ID does not exist.
        """
        if discovery.id in self.discoveries:
            raise DuplicateIdError(f"Discovery {discovery.id} already exists")
        self._check_refs_exist(discovery.related_hypotheses, self.hypotheses, "hypothesis")
        self._check_refs_exist(discovery.related_predictions, self.predictions, "prediction")
        new = self._copy()
        new.discoveries[discovery.id] = copy.deepcopy(discovery)
        return new

    def register_dead_end(self, dead_end: DeadEnd) -> EpistemicGraph:
        """Register a new dead end record in the graph.

        Validates that all ``related_hypotheses`` and ``related_predictions``
        IDs exist.

        Args:
            dead_end: The dead end to register. Must have a unique ``id``.

        Returns:
            EpistemicGraph: A new graph instance containing the registered dead end.

        Raises:
            DuplicateIdError: If ``dead_end.id`` already exists.
            BrokenReferenceError: If any referenced ID does not exist.
        """
        if dead_end.id in self.dead_ends:
            raise DuplicateIdError(f"DeadEnd {dead_end.id} already exists")
        self._check_refs_exist(dead_end.related_hypotheses, self.hypotheses, "hypothesis")
        self._check_refs_exist(dead_end.related_predictions, self.predictions, "prediction")
        new = self._copy()
        new.dead_ends[dead_end.id] = copy.deepcopy(dead_end)
        return new

    def register_parameter(self, parameter: Parameter) -> EpistemicGraph:
        """Register a new parameter constant in the graph.

        ``used_in_analyses`` is a backlink owned by analysis operations
        and starts empty.

        Args:
            parameter: The parameter to register. Must have a unique ``id``.

        Returns:
            EpistemicGraph: A new graph instance containing the registered parameter.

        Raises:
            DuplicateIdError: If ``parameter.id`` already exists.
        """
        if parameter.id in self.parameters:
            raise DuplicateIdError(f"Parameter {parameter.id} already exists")
        new = self._copy()
        stored = copy.deepcopy(parameter)
        stored.used_in_analyses = set()
        new.parameters[parameter.id] = stored
        return new

    def add_pairwise_separation(self, sep: PairwiseSeparation) -> EpistemicGraph:
        """Register a pairwise separation record between two independence groups.

        Documents why two independence groups provide genuinely separate
        evidence. Both groups must already exist and must be distinct.

        Args:
            sep: The separation record to register. Must have a unique ``id``.

        Returns:
            EpistemicGraph: A new graph instance containing the registered separation.

        Raises:
            DuplicateIdError: If ``sep.id`` already exists.
            BrokenReferenceError: If either group does not exist or both
                groups are the same.
        """
        if sep.id in self.pairwise_separations:
            raise DuplicateIdError(f"PairwiseSeparation {sep.id} already exists")
        if sep.group_a == sep.group_b:
            raise BrokenReferenceError("Pairwise separation requires two distinct groups")
        if sep.group_a not in self.independence_groups:
            raise BrokenReferenceError(f"Group {sep.group_a} does not exist")
        if sep.group_b not in self.independence_groups:
            raise BrokenReferenceError(f"Group {sep.group_b} does not exist")
        new = self._copy()
        new.pairwise_separations[sep.id] = copy.deepcopy(sep)
        return new

    def transition_prediction(
        self, pid: PredictionId, new_status: PredictionStatus
    ) -> EpistemicGraph:
        """Change a prediction's lifecycle status.

        Args:
            pid: The prediction ID to transition.
            new_status: The new status to assign.

        Returns:
            EpistemicGraph: A new graph instance with the updated status.

        Raises:
            BrokenReferenceError: If the prediction does not exist.
        """
        if pid not in self.predictions:
            raise BrokenReferenceError(f"Prediction {pid} does not exist")
        new = self._copy()
        new.predictions[pid] = copy.deepcopy(new.predictions[pid])
        new.predictions[pid].status = new_status
        return new

    def transition_dead_end(
        self,
        did: DeadEndId,
        new_status: DeadEndStatus,
    ) -> EpistemicGraph:
        """Change a dead end's lifecycle status.

        Args:
            did: The dead end ID to transition.
            new_status: The new status to assign (ACTIVE, RESOLVED, or ARCHIVED).

        Returns:
            EpistemicGraph: A new graph instance with the updated status.

        Raises:
            BrokenReferenceError: If the dead end does not exist.
        """
        if did not in self.dead_ends:
            raise BrokenReferenceError(f"DeadEnd {did} does not exist")
        new = self._copy()
        new.dead_ends[did] = copy.deepcopy(new.dead_ends[did])
        new.dead_ends[did].status = new_status
        return new

    def transition_hypothesis(self, cid: HypothesisId, new_status: HypothesisStatus) -> EpistemicGraph:
        """Change a hypothesis's lifecycle status.

        Args:
            cid: The hypothesis ID to transition.
            new_status: The new status (ACTIVE, REVISED, or RETRACTED).

        Returns:
            EpistemicGraph: A new graph instance with the updated status.

        Raises:
            BrokenReferenceError: If the hypothesis does not exist.
        """
        if cid not in self.hypotheses:
            raise BrokenReferenceError(f"Hypothesis {cid} does not exist")
        new = self._copy()
        new.hypotheses[cid] = copy.deepcopy(new.hypotheses[cid])
        new.hypotheses[cid].status = new_status
        return new

    def transition_objective(self, tid: ObjectiveId, new_status: ObjectiveStatus) -> EpistemicGraph:
        """Change a objective's lifecycle status.

        Args:
            tid: The objective ID to transition.
            new_status: The new status (ACTIVE, REFINED, ABANDONED, or SUPERSEDED).

        Returns:
            EpistemicGraph: A new graph instance with the updated status.

        Raises:
            BrokenReferenceError: If the objective does not exist.
        """
        if tid not in self.objectives:
            raise BrokenReferenceError(f"Objective {tid} does not exist")
        new = self._copy()
        new.objectives[tid] = copy.deepcopy(new.objectives[tid])
        new.objectives[tid].status = new_status
        return new

    def transition_discovery(self, did: DiscoveryId, new_status: DiscoveryStatus) -> EpistemicGraph:
        """Change a discovery's lifecycle status.

        Args:
            did: The discovery ID to transition.
            new_status: The new status (NEW, INTEGRATED, or ARCHIVED).

        Returns:
            EpistemicGraph: A new graph instance with the updated status.

        Raises:
            BrokenReferenceError: If the discovery does not exist.
        """
        if did not in self.discoveries:
            raise BrokenReferenceError(f"Discovery {did} does not exist")
        new = self._copy()
        new.discoveries[did] = copy.deepcopy(new.discoveries[did])
        new.discoveries[did].status = new_status
        return new

    def record_analysis_result(
        self,
        anid: AnalysisId,
        result: object,
        *,
        git_sha: str | None = None,
        result_date: date | None = None,
    ) -> EpistemicGraph:
        """Record the output of a completed analysis run.

        Sets ``last_result``, ``last_result_sha``, and ``last_result_date``
        on the analysis while preserving every other field (path, command,
        uses_parameters, hypotheses_covered) exactly as-is.

        This is intentionally a narrow mutation — the researcher records
        what came out of running the analysis without touching any of the
        provenance or structural metadata.

        Args:
            anid: The analysis ID to record a result for.
            result: The output value of the analysis run.
            git_sha: Optional git SHA of the analysis code at run time.
            result_date: Optional date when the result was recorded.

        Returns:
            EpistemicGraph: A new graph instance with the analysis result recorded.

        Raises:
            BrokenReferenceError: If the analysis does not exist.
        """
        if anid not in self.analyses:
            raise BrokenReferenceError(f"Analysis {anid} does not exist")
        new = self._copy()
        new.analyses[anid] = copy.deepcopy(new.analyses[anid])
        new.analyses[anid].last_result = result
        new.analyses[anid].last_result_sha = git_sha
        new.analyses[anid].last_result_date = result_date
        return new

    # ── Update mutations — re-links bidirectional relationships ───

    def update_hypothesis(self, new_hypothesis: Hypothesis) -> EpistemicGraph:
        """Replace a hypothesis's fields while maintaining all bidirectional links.

        The new hypothesis must have the same ID as an existing hypothesis. Diffs
        old vs new link sets for assumptions and analyses, removing stale
        backlinks and adding new ones. Validates new refs exist and that
        no dependency cycle is introduced.

        Args:
            new_hypothesis: The updated hypothesis. Must have the same ``id`` as
                an existing hypothesis in the graph.

        Returns:
            EpistemicGraph: A new graph instance with the updated hypothesis and
                corrected bidirectional links.

        Raises:
            BrokenReferenceError: If the hypothesis does not exist or if any
                newly referenced ID does not exist.
            CycleError: If the updated ``depends_on`` would create a cycle.
        """
        if new_hypothesis.id not in self.hypotheses:
            raise BrokenReferenceError(f"Hypothesis {new_hypothesis.id} does not exist")
        old = self.hypotheses[new_hypothesis.id]
        self._check_refs_exist(new_hypothesis.assumptions, self.assumptions, "assumption")
        self._check_refs_exist(new_hypothesis.depends_on, self.hypotheses, "hypothesis")
        self._check_refs_exist(new_hypothesis.analyses, self.analyses, "analysis")
        self._check_refs_exist(set(new_hypothesis.parameter_constraints.keys()), self.parameters, "parameter")
        self._check_refs_exist(new_hypothesis.objectives, self.objectives, "objective")
        self._check_no_cycle_with(new_hypothesis)

        new = self._copy()
        new.hypotheses[new_hypothesis.id] = copy.deepcopy(new_hypothesis)

        # Diff assumption.used_in_hypotheses
        for aid in old.assumptions - new_hypothesis.assumptions:
            new.assumptions[aid] = copy.deepcopy(new.assumptions[aid])
            new.assumptions[aid].used_in_hypotheses.discard(new_hypothesis.id)
        for aid in new_hypothesis.assumptions - old.assumptions:
            new.assumptions[aid] = copy.deepcopy(new.assumptions[aid])
            new.assumptions[aid].used_in_hypotheses.add(new_hypothesis.id)

        # Diff analysis.hypotheses_covered
        for anid in old.analyses - new_hypothesis.analyses:
            new.analyses[anid] = copy.deepcopy(new.analyses[anid])
            new.analyses[anid].hypotheses_covered.discard(new_hypothesis.id)
        for anid in new_hypothesis.analyses - old.analyses:
            new.analyses[anid] = copy.deepcopy(new.analyses[anid])
            new.analyses[anid].hypotheses_covered.add(new_hypothesis.id)

        # Diff objective.motivates_hypotheses
        for tid in old.objectives - new_hypothesis.objectives:
            new.objectives[tid] = copy.deepcopy(new.objectives[tid])
            new.objectives[tid].motivates_hypotheses.discard(new_hypothesis.id)
        for tid in new_hypothesis.objectives - old.objectives:
            new.objectives[tid] = copy.deepcopy(new.objectives[tid])
            new.objectives[tid].motivates_hypotheses.add(new_hypothesis.id)

        return new

    def update_assumption(self, new_assumption: Assumption) -> EpistemicGraph:
        """Replace an assumption's fields, preserving owned backlinks.

        ``used_in_hypotheses`` and ``tested_by`` are maintained by hypothesis and
        prediction operations respectively — they are preserved from the
        old assumption. Only ``depends_on`` chain changes need validation.

        Args:
            new_assumption: The updated assumption. Must have the same ``id``
                as an existing assumption.

        Returns:
            EpistemicGraph: A new graph instance with the updated assumption.

        Raises:
            BrokenReferenceError: If the assumption does not exist or if
                any ``depends_on`` ID does not exist.
            CycleError: If the updated ``depends_on`` would create a cycle.
        """
        if new_assumption.id not in self.assumptions:
            raise BrokenReferenceError(f"Assumption {new_assumption.id} does not exist")
        old = self.assumptions[new_assumption.id]
        self._check_refs_exist(new_assumption.depends_on, self.assumptions, "assumption")
        self._check_no_assumption_cycle_with(new_assumption)

        new = self._copy()
        # Preserve backlinks that are owned by other entities
        updated = copy.deepcopy(new_assumption)
        updated.used_in_hypotheses = copy.deepcopy(old.used_in_hypotheses)
        updated.tested_by = copy.deepcopy(old.tested_by)
        new.assumptions[new_assumption.id] = updated
        return new

    def update_prediction(self, new_prediction: Prediction) -> EpistemicGraph:
        """Replace a prediction's fields while maintaining all bidirectional links.

        Diffs old vs new ``tests_assumptions`` and ``independence_group``
        sets, updating backlinks on assumptions and independence groups
        accordingly.

        Args:
            new_prediction: The updated prediction. Must have the same ``id``
                as an existing prediction.

        Returns:
            EpistemicGraph: A new graph instance with the updated prediction and
                corrected bidirectional links.

        Raises:
            BrokenReferenceError: If the prediction does not exist or if
                any newly referenced ID does not exist.
        """
        if new_prediction.id not in self.predictions:
            raise BrokenReferenceError(f"Prediction {new_prediction.id} does not exist")
        old = self.predictions[new_prediction.id]
        self._check_refs_exist(new_prediction.hypothesis_ids, self.hypotheses, "hypothesis")
        self._check_refs_exist(new_prediction.tests_assumptions, self.assumptions, "assumption")
        self._check_refs_exist(new_prediction.conditional_on, self.assumptions, "assumption")
        if new_prediction.analysis and new_prediction.analysis not in self.analyses:
            raise BrokenReferenceError(f"Analysis {new_prediction.analysis} does not exist")
        if new_prediction.independence_group and new_prediction.independence_group not in self.independence_groups:
            raise BrokenReferenceError(f"Independence group {new_prediction.independence_group} does not exist")

        new = self._copy()
        new.predictions[new_prediction.id] = copy.deepcopy(new_prediction)

        # Diff assumption.tested_by
        for aid in old.tests_assumptions - new_prediction.tests_assumptions:
            new.assumptions[aid] = copy.deepcopy(new.assumptions[aid])
            new.assumptions[aid].tested_by.discard(new_prediction.id)
        for aid in new_prediction.tests_assumptions - old.tests_assumptions:
            new.assumptions[aid] = copy.deepcopy(new.assumptions[aid])
            new.assumptions[aid].tested_by.add(new_prediction.id)

        # Diff independence_group.member_predictions
        if old.independence_group != new_prediction.independence_group:
            if old.independence_group and old.independence_group in new.independence_groups:
                old_gid = old.independence_group
                new.independence_groups[old_gid] = copy.deepcopy(new.independence_groups[old_gid])
                new.independence_groups[old_gid].member_predictions.discard(new_prediction.id)
            if new_prediction.independence_group and new_prediction.independence_group in new.independence_groups:
                new_gid = new_prediction.independence_group
                new.independence_groups[new_gid] = copy.deepcopy(new.independence_groups[new_gid])
                new.independence_groups[new_gid].member_predictions.add(new_prediction.id)

        return new

    def update_parameter(self, new_parameter: Parameter) -> EpistemicGraph:
        """Replace a parameter's fields (value, unit, uncertainty, etc.).

        ``used_in_analyses`` is a backlink maintained by analysis operations
        — it is preserved from the old parameter so callers cannot
        accidentally corrupt the staleness tracking index.

        Args:
            new_parameter: The updated parameter. Must have the same ``id``
                as an existing parameter.

        Returns:
            EpistemicGraph: A new graph instance with the updated parameter.

        Raises:
            BrokenReferenceError: If the parameter does not exist.
        """
        if new_parameter.id not in self.parameters:
            raise BrokenReferenceError(f"Parameter {new_parameter.id} does not exist")
        old = self.parameters[new_parameter.id]
        new = self._copy()
        updated = copy.deepcopy(new_parameter)
        updated.used_in_analyses = copy.deepcopy(old.used_in_analyses)
        new.parameters[new_parameter.id] = updated
        return new

    def update_analysis(self, new_analysis: Analysis) -> EpistemicGraph:
        """Replace an analysis's fields while maintaining bidirectional links.

        ``hypotheses_covered`` is a backlink maintained by hypothesis operations and
        is preserved as-is. Diffs ``uses_parameters`` and updates
        ``Parameter.used_in_analyses`` accordingly.

        Args:
            new_analysis: The updated analysis. Must have the same ``id``
                as an existing analysis.

        Returns:
            EpistemicGraph: A new graph instance with the updated analysis and
                corrected parameter backlinks.

        Raises:
            BrokenReferenceError: If the analysis does not exist or if
                any ``uses_parameters`` ID does not exist.
        """
        if new_analysis.id not in self.analyses:
            raise BrokenReferenceError(f"Analysis {new_analysis.id} does not exist")
        old = self.analyses[new_analysis.id]
        self._check_refs_exist(new_analysis.uses_parameters, self.parameters, "parameter")

        new = self._copy()
        updated = copy.deepcopy(new_analysis)
        # Preserve backlink owned by hypothesis operations
        updated.hypotheses_covered = copy.deepcopy(old.hypotheses_covered)
        new.analyses[new_analysis.id] = updated

        # Diff parameter.used_in_analyses
        for pid in old.uses_parameters - new_analysis.uses_parameters:
            if pid in new.parameters:
                new.parameters[pid] = copy.deepcopy(new.parameters[pid])
                new.parameters[pid].used_in_analyses.discard(new_analysis.id)
        for pid in new_analysis.uses_parameters - old.uses_parameters:
            new.parameters[pid] = copy.deepcopy(new.parameters[pid])
            new.parameters[pid].used_in_analyses.add(new_analysis.id)

        return new

    def update_objective(self, new_objective: Objective) -> EpistemicGraph:
        """Replace an objective's fields.

        Validates that all ``related_predictions``, ``related_dead_ends``,
        and ``related_discoveries`` IDs exist.
        ``motivates_hypotheses`` is a backlink maintained by hypothesis operations
        and is preserved from the existing objective.

        Args:
            new_objective: The updated objective. Must have the same ``id``
                as an existing objective.

        Returns:
            EpistemicGraph: A new graph instance with the updated objective.

        Raises:
            BrokenReferenceError: If the objective does not exist or if
                any referenced ID does not exist.
        """
        if new_objective.id not in self.objectives:
            raise BrokenReferenceError(f"Objective {new_objective.id} does not exist")
        old = self.objectives[new_objective.id]
        self._check_refs_exist(new_objective.related_predictions, self.predictions, "prediction")
        self._check_refs_exist(new_objective.related_dead_ends, self.dead_ends, "dead_end")
        self._check_refs_exist(new_objective.related_discoveries, self.discoveries, "discovery")
        new = self._copy()
        updated = copy.deepcopy(new_objective)
        updated.motivates_hypotheses = copy.deepcopy(old.motivates_hypotheses)
        new.objectives[new_objective.id] = updated
        return new

    def update_independence_group(self, new_group: IndependenceGroup) -> EpistemicGraph:
        """Replace an independence group's annotation fields.

        ``member_predictions`` is a backlink maintained by prediction
        operations — preserved from the existing group. Validates
        ``hypothesis_lineage`` and ``assumption_lineage`` refs.

        Args:
            new_group: The updated independence group. Must have the same
                ``id`` as an existing group.

        Returns:
            EpistemicGraph: A new graph instance with the updated group.

        Raises:
            BrokenReferenceError: If the group does not exist or if
                any lineage ID does not exist.
        """
        if new_group.id not in self.independence_groups:
            raise BrokenReferenceError(f"IndependenceGroup {new_group.id} does not exist")
        old = self.independence_groups[new_group.id]
        self._check_refs_exist(new_group.hypothesis_lineage, self.hypotheses, "hypothesis")
        self._check_refs_exist(new_group.assumption_lineage, self.assumptions, "assumption")

        new = self._copy()
        updated = copy.deepcopy(new_group)
        updated.member_predictions = copy.deepcopy(old.member_predictions)
        new.independence_groups[new_group.id] = updated
        return new

    def update_pairwise_separation(self, new_sep: PairwiseSeparation) -> EpistemicGraph:
        """Replace a pairwise separation record's fields.

        Validates that both referenced groups still exist and are distinct.

        Args:
            new_sep: The updated separation record. Must have the same ``id``
                as an existing record.

        Returns:
            EpistemicGraph: A new graph instance with the updated separation.

        Raises:
            BrokenReferenceError: If the separation does not exist, if either
                group does not exist, or if both groups are the same.
        """
        if new_sep.id not in self.pairwise_separations:
            raise BrokenReferenceError(f"PairwiseSeparation {new_sep.id} does not exist")
        if new_sep.group_a == new_sep.group_b:
            raise BrokenReferenceError("Pairwise separation requires two distinct groups")
        if new_sep.group_a not in self.independence_groups:
            raise BrokenReferenceError(f"Group {new_sep.group_a} does not exist")
        if new_sep.group_b not in self.independence_groups:
            raise BrokenReferenceError(f"Group {new_sep.group_b} does not exist")
        new = self._copy()
        new.pairwise_separations[new_sep.id] = copy.deepcopy(new_sep)
        return new

    def update_discovery(self, new_discovery: Discovery) -> EpistemicGraph:
        """Replace a discovery's fields.

        Validates that all ``related_hypotheses`` and ``related_predictions``
        IDs exist.

        Args:
            new_discovery: The updated discovery. Must have the same ``id``
                as an existing discovery.

        Returns:
            EpistemicGraph: A new graph instance with the updated discovery.

        Raises:
            BrokenReferenceError: If the discovery does not exist or if
                any referenced ID does not exist.
        """
        if new_discovery.id not in self.discoveries:
            raise BrokenReferenceError(f"Discovery {new_discovery.id} does not exist")
        self._check_refs_exist(new_discovery.related_hypotheses, self.hypotheses, "hypothesis")
        self._check_refs_exist(new_discovery.related_predictions, self.predictions, "prediction")
        new = self._copy()
        new.discoveries[new_discovery.id] = copy.deepcopy(new_discovery)
        return new

    def update_dead_end(self, new_dead_end: DeadEnd) -> EpistemicGraph:
        """Replace a dead end's fields.

        Validates that all ``related_hypotheses`` and ``related_predictions``
        IDs exist.

        Args:
            new_dead_end: The updated dead end. Must have the same ``id``
                as an existing dead end.

        Returns:
            EpistemicGraph: A new graph instance with the updated dead end.

        Raises:
            BrokenReferenceError: If the dead end does not exist or if
                any referenced ID does not exist.
        """
        if new_dead_end.id not in self.dead_ends:
            raise BrokenReferenceError(f"DeadEnd {new_dead_end.id} does not exist")
        self._check_refs_exist(new_dead_end.related_hypotheses, self.hypotheses, "hypothesis")
        self._check_refs_exist(new_dead_end.related_predictions, self.predictions, "prediction")
        new = self._copy()
        new.dead_ends[new_dead_end.id] = copy.deepcopy(new_dead_end)
        return new

    # ── Remove mutations — safe deletion with ref checks ──────────

    def remove_prediction(self, pid: PredictionId) -> EpistemicGraph:
        """Remove a prediction from the graph.

        Tears down all backlinks (``Assumption.tested_by``,
        ``IndependenceGroup.member_predictions``) and scrubs soft
        navigational references in objectives, dead ends, and discoveries.
        No entity hard-blocks prediction removal.

        Args:
            pid: The prediction ID to remove.

        Returns:
            EpistemicGraph: A new graph instance without the prediction.

        Raises:
            BrokenReferenceError: If the prediction does not exist.
        """
        if pid not in self.predictions:
            raise BrokenReferenceError(f"Prediction {pid} does not exist")
        pred = self.predictions[pid]
        new = self._copy()
        del new.predictions[pid]
        for aid in pred.tests_assumptions:
            if aid in new.assumptions:
                new.assumptions[aid] = copy.deepcopy(new.assumptions[aid])
                new.assumptions[aid].tested_by.discard(pid)
        if pred.independence_group and pred.independence_group in new.independence_groups:
            gid = pred.independence_group
            new.independence_groups[gid] = copy.deepcopy(new.independence_groups[gid])
            new.independence_groups[gid].member_predictions.discard(pid)
        # Scrub soft references in objectives, dead ends, and discoveries
        for tid, objective in list(new.objectives.items()):
            if pid in objective.related_predictions:
                new.objectives[tid] = copy.deepcopy(objective)
                new.objectives[tid].related_predictions.discard(pid)
        for de_id, dead_end in list(new.dead_ends.items()):
            if pid in dead_end.related_predictions:
                new.dead_ends[de_id] = copy.deepcopy(dead_end)
                new.dead_ends[de_id].related_predictions.discard(pid)
        for disc_id, discovery in list(new.discoveries.items()):
            if pid in discovery.related_predictions:
                new.discoveries[disc_id] = copy.deepcopy(discovery)
                new.discoveries[disc_id].related_predictions.discard(pid)
        # Scrub observation.predictions links (observation owns the forward link)
        for oid, obs in list(new.observations.items()):
            if pid in obs.predictions:
                new.observations[oid] = copy.deepcopy(obs)
                new.observations[oid].predictions.discard(pid)
        return new

    def remove_hypothesis(self, cid: HypothesisId) -> EpistemicGraph:
        """Remove a hypothesis from the graph.

        Raises if any other hypothesis's ``depends_on`` or any prediction's
        ``hypothesis_ids`` still references this hypothesis. Callers must first
        update or remove all referencing entities.

        On success, tears down backlinks on assumptions and analyses,
        scrubs soft references in objectives, dead ends, discoveries,
        and independence group ``hypothesis_lineage`` annotations.

        Args:
            cid: The hypothesis ID to remove.

        Returns:
            EpistemicGraph: A new graph instance without the hypothesis.

        Raises:
            BrokenReferenceError: If the hypothesis does not exist or is still
                referenced by other hypotheses or predictions.
        """
        if cid not in self.hypotheses:
            raise BrokenReferenceError(f"Hypothesis {cid} does not exist")
        blocking_hypotheses = [
            c_id for c_id, c in self.hypotheses.items()
            if cid in c.depends_on and c_id != cid
        ]
        blocking_preds = [
            p_id for p_id, p in self.predictions.items()
            if cid in p.hypothesis_ids
        ]
        if blocking_hypotheses or blocking_preds:
            raise BrokenReferenceError(
                f"Hypothesis {cid} is still referenced by "
                f"hypotheses {blocking_hypotheses} and predictions {blocking_preds}"
            )
        hypothesis = self.hypotheses[cid]
        new = self._copy()
        del new.hypotheses[cid]
        for aid in hypothesis.assumptions:
            if aid in new.assumptions:
                new.assumptions[aid] = copy.deepcopy(new.assumptions[aid])
                new.assumptions[aid].used_in_hypotheses.discard(cid)
        for anid in hypothesis.analyses:
            if anid in new.analyses:
                new.analyses[anid] = copy.deepcopy(new.analyses[anid])
                new.analyses[anid].hypotheses_covered.discard(cid)
        # Tear down bidirectional: objective.motivates_hypotheses
        for tid in hypothesis.objectives:
            if tid in new.objectives:
                new.objectives[tid] = copy.deepcopy(new.objectives[tid])
                new.objectives[tid].motivates_hypotheses.discard(cid)
        # Scrub soft references in dead ends and discoveries
        for de_id, dead_end in list(new.dead_ends.items()):
            if cid in dead_end.related_hypotheses:
                new.dead_ends[de_id] = copy.deepcopy(dead_end)
                new.dead_ends[de_id].related_hypotheses.discard(cid)
        for disc_id, discovery in list(new.discoveries.items()):
            if cid in discovery.related_hypotheses:
                new.discoveries[disc_id] = copy.deepcopy(discovery)
                new.discoveries[disc_id].related_hypotheses.discard(cid)
        # Scrub soft references in observations
        for oid, obs in list(new.observations.items()):
            if cid in obs.related_hypotheses:
                new.observations[oid] = copy.deepcopy(obs)
                new.observations[oid].related_hypotheses.discard(cid)
        # Scrub hypothesis_lineage annotations in independence groups
        for gid, group in list(new.independence_groups.items()):
            if cid in group.hypothesis_lineage:
                new.independence_groups[gid] = copy.deepcopy(group)
                new.independence_groups[gid].hypothesis_lineage.discard(cid)
        return new

    def remove_assumption(self, aid: AssumptionId) -> EpistemicGraph:
        """Remove an assumption from the graph.

        Raises if any hypothesis, prediction, or other assumption still
        references this assumption. Scrubs ``assumption_lineage``
        annotations in independence groups on success.

        Args:
            aid: The assumption ID to remove.

        Returns:
            EpistemicGraph: A new graph instance without the assumption.

        Raises:
            BrokenReferenceError: If the assumption does not exist or is
                still referenced by hypotheses, predictions, or other assumptions.
        """
        if aid not in self.assumptions:
            raise BrokenReferenceError(f"Assumption {aid} does not exist")
        blocking_hypotheses = [
            c_id for c_id, c in self.hypotheses.items() if aid in c.assumptions
        ]
        blocking_preds = [
            p_id for p_id, p in self.predictions.items()
            if aid in p.tests_assumptions or aid in p.conditional_on
        ]
        blocking_assumptions = [
            a_id for a_id, a in self.assumptions.items()
            if aid in a.depends_on and a_id != aid
        ]
        if blocking_hypotheses or blocking_preds or blocking_assumptions:
            raise BrokenReferenceError(
                f"Assumption {aid} is still referenced by "
                f"hypotheses {blocking_hypotheses}, predictions {blocking_preds}, "
                f"assumptions {blocking_assumptions}"
            )
        new = self._copy()
        del new.assumptions[aid]
        # Scrub assumption_lineage annotations in independence groups
        for gid, group in list(new.independence_groups.items()):
            if aid in group.assumption_lineage:
                new.independence_groups[gid] = copy.deepcopy(group)
                new.independence_groups[gid].assumption_lineage.discard(aid)
        # Scrub soft references in observations
        for oid, obs in list(new.observations.items()):
            if aid in obs.related_assumptions:
                new.observations[oid] = copy.deepcopy(obs)
                new.observations[oid].related_assumptions.discard(aid)
        return new

    def remove_parameter(self, pid: ParameterId) -> EpistemicGraph:
        """Remove a parameter from the graph.

        Raises if any analysis still references this parameter via
        ``uses_parameters``. On success, cleans up dangling
        ``parameter_constraints`` annotations on hypotheses.

        Args:
            pid: The parameter ID to remove.

        Returns:
            EpistemicGraph: A new graph instance without the parameter.

        Raises:
            BrokenReferenceError: If the parameter does not exist or is
                still used by analyses.
        """
        if pid not in self.parameters:
            raise BrokenReferenceError(f"Parameter {pid} does not exist")
        blocking_analyses = [
            a_id for a_id, a in self.analyses.items()
            if pid in a.uses_parameters
        ]
        if blocking_analyses:
            raise BrokenReferenceError(
                f"Parameter {pid} is still used by analyses {blocking_analyses}"
            )
        new = self._copy()
        del new.parameters[pid]
        # Clean up dangling constraint annotations on hypotheses
        for cid, hypothesis in list(new.hypotheses.items()):
            if pid in hypothesis.parameter_constraints:
                new.hypotheses[cid] = copy.deepcopy(hypothesis)
                new.hypotheses[cid].parameter_constraints.pop(pid, None)
        return new

    def remove_analysis(self, anid: AnalysisId) -> EpistemicGraph:
        """Remove an analysis from the graph.

        Raises if any hypothesis's ``analyses`` or any prediction's ``analysis``
        still references this analysis. Tears down
        ``Parameter.used_in_analyses`` backlinks on success.

        Args:
            anid: The analysis ID to remove.

        Returns:
            EpistemicGraph: A new graph instance without the analysis.

        Raises:
            BrokenReferenceError: If the analysis does not exist or is
                still referenced by hypotheses or predictions.
        """
        if anid not in self.analyses:
            raise BrokenReferenceError(f"Analysis {anid} does not exist")
        blocking_hypotheses = [
            cid for cid, c in self.hypotheses.items() if anid in c.analyses
        ]
        blocking_preds = [
            pid for pid, p in self.predictions.items() if p.analysis == anid
        ]
        if blocking_hypotheses or blocking_preds:
            raise BrokenReferenceError(
                f"Analysis {anid} is still referenced by "
                f"hypotheses {blocking_hypotheses} and predictions {blocking_preds}"
            )
        analysis = self.analyses[anid]
        new = self._copy()
        del new.analyses[anid]
        for pid in analysis.uses_parameters:
            if pid in new.parameters:
                new.parameters[pid] = copy.deepcopy(new.parameters[pid])
                new.parameters[pid].used_in_analyses.discard(anid)
        return new

    def remove_independence_group(self, gid: IndependenceGroupId) -> EpistemicGraph:
        """Remove an independence group from the graph.

        Raises if any prediction's ``independence_group`` or any pairwise
        separation still references this group.

        Args:
            gid: The independence group ID to remove.

        Returns:
            EpistemicGraph: A new graph instance without the group.

        Raises:
            BrokenReferenceError: If the group does not exist or is still
                referenced by predictions or separations.
        """
        if gid not in self.independence_groups:
            raise BrokenReferenceError(f"IndependenceGroup {gid} does not exist")
        blocking_preds = [
            pid for pid, p in self.predictions.items()
            if p.independence_group == gid
        ]
        blocking_seps = [
            sid for sid, s in self.pairwise_separations.items()
            if s.group_a == gid or s.group_b == gid
        ]
        if blocking_preds or blocking_seps:
            raise BrokenReferenceError(
                f"IndependenceGroup {gid} is still referenced by "
                f"predictions {blocking_preds} and separations {blocking_seps}"
            )
        new = self._copy()
        del new.independence_groups[gid]
        return new

    def remove_objective(self, tid: ObjectiveId) -> EpistemicGraph:
        """Remove an objective from the graph.

        Scrubs ``Hypothesis.objectives`` references on any hypotheses that were
        motivated by this objective. Does not block on hypotheses — a hypothesis
        can survive without its motivating objective.

        Args:
            tid: The objective ID to remove.

        Returns:
            EpistemicGraph: A new graph instance without the objective.

        Raises:
            BrokenReferenceError: If the objective does not exist.
        """
        if tid not in self.objectives:
            raise BrokenReferenceError(f"Objective {tid} does not exist")
        new = self._copy()
        del new.objectives[tid]
        # Scrub Hypothesis.objectives backlinks
        for cid, hypothesis in list(new.hypotheses.items()):
            if tid in hypothesis.objectives:
                new.hypotheses[cid] = copy.deepcopy(hypothesis)
                new.hypotheses[cid].objectives.discard(tid)
        return new

    def remove_discovery(self, did: DiscoveryId) -> EpistemicGraph:
        """Remove a discovery from the graph.

        Discoveries are leaf entities — nothing references them by ID, so
        removal is always safe.

        Args:
            did: The discovery ID to remove.

        Returns:
            EpistemicGraph: A new graph instance without the discovery.

        Raises:
            BrokenReferenceError: If the discovery does not exist.
        """
        if did not in self.discoveries:
            raise BrokenReferenceError(f"Discovery {did} does not exist")
        new = self._copy()
        del new.discoveries[did]
        # Scrub Objective.related_discoveries soft links
        for oid, obj in list(new.objectives.items()):
            if did in obj.related_discoveries:
                new.objectives[oid] = copy.deepcopy(obj)
                new.objectives[oid].related_discoveries.discard(did)
        return new

    def remove_dead_end(self, did: DeadEndId) -> EpistemicGraph:
        """Remove a dead end from the graph.

        Dead ends are leaf entities — nothing references them by ID, so
        removal is always safe.

        Args:
            did: The dead end ID to remove.

        Returns:
            EpistemicGraph: A new graph instance without the dead end.

        Raises:
            BrokenReferenceError: If the dead end does not exist.
        """
        if did not in self.dead_ends:
            raise BrokenReferenceError(f"DeadEnd {did} does not exist")
        new = self._copy()
        del new.dead_ends[did]
        # Scrub Objective.related_dead_ends soft links
        for oid, obj in list(new.objectives.items()):
            if did in obj.related_dead_ends:
                new.objectives[oid] = copy.deepcopy(obj)
                new.objectives[oid].related_dead_ends.discard(did)
        return new

    def remove_pairwise_separation(self, sid: PairwiseSeparationId) -> EpistemicGraph:
        """Remove a pairwise separation record from the graph.

        Args:
            sid: The separation record ID to remove.

        Returns:
            EpistemicGraph: A new graph instance without the separation record.

        Raises:
            BrokenReferenceError: If the separation does not exist.
        """
        if sid not in self.pairwise_separations:
            raise BrokenReferenceError(f"PairwiseSeparation {sid} does not exist")
        new = self._copy()
        del new.pairwise_separations[sid]
        return new

    def register_observation(self, observation: Observation) -> EpistemicGraph:
        """Register a new observation in the graph.

        Validates that all referenced predictions, hypotheses, and assumptions
        exist. Updates bidirectional ``Prediction.observations`` backlinks.

        Args:
            observation: The observation to register. Must have a unique ``id``.

        Returns:
            EpistemicGraph: A new graph instance containing the registered observation.

        Raises:
            DuplicateIdError: If ``observation.id`` already exists.
            BrokenReferenceError: If any referenced ID does not exist.
        """
        if observation.id in self.observations:
            raise DuplicateIdError(f"Observation {observation.id} already exists")
        self._check_refs_exist(observation.predictions, self.predictions, "prediction")
        self._check_refs_exist(observation.related_hypotheses, self.hypotheses, "hypothesis")
        self._check_refs_exist(observation.related_assumptions, self.assumptions, "assumption")

        new = self._copy()
        new.observations[observation.id] = copy.deepcopy(observation)

        # Maintain bidirectional: prediction.observations
        for pid in observation.predictions:
            new.predictions[pid] = copy.deepcopy(new.predictions[pid])
            new.predictions[pid].observations.add(observation.id)

        return new

    def update_observation(self, new_observation: Observation) -> EpistemicGraph:
        """Replace an observation's fields while maintaining bidirectional links.

        Diffs old vs new ``predictions`` sets and updates
        ``Prediction.observations`` backlinks accordingly.

        Args:
            new_observation: The updated observation. Must have the same
                ``id`` as an existing observation.

        Returns:
            EpistemicGraph: A new graph instance with the updated observation.

        Raises:
            BrokenReferenceError: If the observation does not exist or if
                any referenced ID does not exist.
        """
        if new_observation.id not in self.observations:
            raise BrokenReferenceError(f"Observation {new_observation.id} does not exist")
        old = self.observations[new_observation.id]
        self._check_refs_exist(new_observation.predictions, self.predictions, "prediction")
        self._check_refs_exist(new_observation.related_hypotheses, self.hypotheses, "hypothesis")
        self._check_refs_exist(new_observation.related_assumptions, self.assumptions, "assumption")

        new = self._copy()
        new.observations[new_observation.id] = copy.deepcopy(new_observation)

        # Diff prediction.observations backlinks
        for pid in old.predictions - new_observation.predictions:
            if pid in new.predictions:
                new.predictions[pid] = copy.deepcopy(new.predictions[pid])
                new.predictions[pid].observations.discard(new_observation.id)
        for pid in new_observation.predictions - old.predictions:
            new.predictions[pid] = copy.deepcopy(new.predictions[pid])
            new.predictions[pid].observations.add(new_observation.id)

        return new

    def remove_observation(self, oid: ObservationId) -> EpistemicGraph:
        """Remove an observation from the graph.

        Tears down ``Prediction.observations`` backlinks. Observations
        are provenance records — nothing else hard-blocks their removal.

        Args:
            oid: The observation ID to remove.

        Returns:
            EpistemicGraph: A new graph instance without the observation.

        Raises:
            BrokenReferenceError: If the observation does not exist.
        """
        if oid not in self.observations:
            raise BrokenReferenceError(f"Observation {oid} does not exist")
        obs = self.observations[oid]
        new = self._copy()
        del new.observations[oid]
        # Tear down prediction.observations backlinks
        for pid in obs.predictions:
            if pid in new.predictions:
                new.predictions[pid] = copy.deepcopy(new.predictions[pid])
                new.predictions[pid].observations.discard(oid)
        return new

    def transition_observation(
        self, oid: ObservationId, new_status: ObservationStatus
    ) -> EpistemicGraph:
        """Change an observation's lifecycle status.

        Args:
            oid: The observation ID to transition.
            new_status: The new status to assign.

        Returns:
            EpistemicGraph: A new graph instance with the updated status.

        Raises:
            BrokenReferenceError: If the observation does not exist.
        """
        if oid not in self.observations:
            raise BrokenReferenceError(f"Observation {oid} does not exist")
        new = self._copy()
        new.observations[oid] = copy.deepcopy(new.observations[oid])
        new.observations[oid].status = new_status
        return new

    # ── Invariant checks ──────────────────────────────────────────

    def _check_refs_exist(self, ids: set, registry: dict, label: str) -> None:
        """Ensure every referenced ID exists in the target registry.

        Args:
            ids: Set of IDs to check.
            registry: The dictionary registry to check against.
            label: Human-readable name of the entity type (used in error messages).

        Raises:
            BrokenReferenceError: When one or more IDs are missing from
                the registry.
        """
        missing = ids - registry.keys()
        if missing:
            raise BrokenReferenceError(f"Non-existent {label}(s): {missing}")

    def _check_no_cycle_with(self, hypothesis: Hypothesis) -> None:
        """Verify that adding this hypothesis would not create a dependency cycle.

        Walks the ``depends_on`` chain starting from the hypothesis's
        dependencies. If the walk encounters the hypothesis's own ID,
        a cycle would result.

        Args:
            hypothesis: The hypothesis about to be registered or updated.

        Raises:
            CycleError: If adding this hypothesis would create a dependency cycle.
        """
        visited: set[HypothesisId] = set()
        stack = list(hypothesis.depends_on)
        while stack:
            current = stack.pop()
            if current == hypothesis.id:
                raise CycleError(
                    f"Adding {hypothesis.id} would create a dependency cycle"
                )
            if current in visited:
                continue
            visited.add(current)
            upstream = self.hypotheses.get(current)
            if upstream:
                stack.extend(upstream.depends_on)

    def _check_no_assumption_cycle_with(self, assumption: Assumption) -> None:
        """Verify that adding this assumption would not create a dependency cycle.

        Walks the assumption ``depends_on`` chain. If the walk encounters
        the assumption's own ID, a cycle would result.

        Args:
            assumption: The assumption about to be registered or updated.

        Raises:
            CycleError: If adding this assumption would create a dependency
                cycle in the assumption graph.
        """
        visited: set[AssumptionId] = set()
        stack = list(assumption.depends_on)
        while stack:
            current = stack.pop()
            if current == assumption.id:
                raise CycleError(
                    f"Adding {assumption.id} would create a dependency cycle in assumptions"
                )
            if current in visited:
                continue
            visited.add(current)
            upstream = self.assumptions.get(current)
            if upstream:
                stack.extend(upstream.depends_on)

    def _copy(self) -> EpistemicGraph:
        """Create a shallow copy for copy-on-write mutation semantics.

        Creates new dict instances for all collections but shares entity
        object references. Each mutation method is responsible for
        deep-copying only the specific entities whose fields it will
        modify (backlink updates, status transitions, field assignments).

        This reduces per-mutation cost from O(N_total_entities) to
        O(N_mutated_entities): a transition that changes one prediction's
        status deep-copies only that prediction, not all 1000.

        Returns:
            EpistemicGraph: A copy with independent dict instances.
        """
        return EpistemicGraph(
            version=self.version,
            hypotheses=dict(self.hypotheses),
            assumptions=dict(self.assumptions),
            predictions=dict(self.predictions),
            objectives=dict(self.objectives),
            discoveries=dict(self.discoveries),
            analyses=dict(self.analyses),
            independence_groups=dict(self.independence_groups),
            pairwise_separations=dict(self.pairwise_separations),
            dead_ends=dict(self.dead_ends),
            parameters=dict(self.parameters),
            observations=dict(self.observations),
        )


# Domain exceptions live in errors.py — imported at the top of this module.
# Re-exported here so that ``from episteme.epistemic.graph import <Error>``
# continues to work for any caller that imports directly from this module.
__all_errors__ = [
    "BrokenReferenceError",
    "CycleError",
    "DuplicateIdError",
    "EpistemicError",
    "InvariantViolation",
]
