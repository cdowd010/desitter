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
    Claim,
    DeadEnd,
    Discovery,
    IndependenceGroup,
    Observation,
    PairwiseSeparation,
    Parameter,
    Prediction,
    Theory,
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
    ClaimId,
    ClaimStatus,
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
    TheoryId,
    TheoryStatus,
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
    ``Assumption.used_in_claims`` ↔ ``Claim.assumptions``,
    ``Parameter.used_in_analyses`` ↔ ``Analysis.uses_parameters``)
    are maintained automatically by the graph's register/update/remove
    methods.

    Attributes:
        claims: Registry of all claims, keyed by ``ClaimId``.
        assumptions: Registry of all assumptions, keyed by ``AssumptionId``.
        predictions: Registry of all predictions, keyed by ``PredictionId``.
        theories: Registry of all theories, keyed by ``TheoryId``.
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
    claims: dict[ClaimId, Claim] = field(default_factory=dict)
    assumptions: dict[AssumptionId, Assumption] = field(default_factory=dict)
    predictions: dict[PredictionId, Prediction] = field(default_factory=dict)
    theories: dict[TheoryId, Theory] = field(default_factory=dict)
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

    def get_claim(self, cid: ClaimId) -> Claim | None:
        """Return a claim by ID, or ``None`` when the claim does not exist.

        Args:
            cid: The unique identifier of the claim to look up.

        Returns:
            Claim | None: The claim instance, or ``None`` if not found.
        """
        return self.claims.get(cid)

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

    def claims_using_assumption(self, aid: AssumptionId) -> set[ClaimId]:
        """Return all claims that reference this assumption in their assumptions set.

        Performs a full scan of all claims. The returned set contains only
        direct references, not transitive ones.

        Args:
            aid: The assumption ID to search for.

        Returns:
            set[ClaimId]: IDs of all claims whose ``assumptions`` field
                contains ``aid``.
        """
        return {cid for cid, c in self.claims.items() if aid in c.assumptions}

    def claim_lineage(self, cid: ClaimId) -> set[ClaimId]:
        """Compute the transitive closure of a claim's ``depends_on`` chain.

        Returns all ancestor claims reachable through the ``depends_on``
        DAG. The input claim itself is NOT included in the result.
        Uses an iterative depth-first traversal.

        Args:
            cid: The claim ID whose ancestors to compute.

        Returns:
            set[ClaimId]: All ancestor claim IDs (transitive ``depends_on``
                closure), excluding ``cid`` itself.
        """
        visited: set[ClaimId] = set()
        stack = [cid]
        while stack:
            current = stack.pop()
            claim = self.claims.get(current)
            if claim is None:
                continue
            for dep in claim.depends_on:
                if dep not in visited:
                    visited.add(dep)
                    stack.append(dep)
        return visited

    def assumption_lineage(self, cid: ClaimId) -> set[AssumptionId]:
        """Return all assumptions reachable through a claim and its ancestors.

        Collects assumptions from the claim and all its transitive
        ancestors (via ``depends_on``), then expands through assumption
        ``depends_on`` chains to capture presupposed assumptions.

        Args:
            cid: The claim ID whose full assumption lineage to compute.

        Returns:
            set[AssumptionId]: All assumption IDs transitively reachable
                through claim and assumption dependency chains.
        """
        all_claims = self.claim_lineage(cid) | {cid}
        direct: set[AssumptionId] = set()
        for ancestor_id in all_claims:
            claim = self.claims.get(ancestor_id)
            if claim:
                direct.update(claim.assumptions)
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

        1. Assumptions from each claim in ``claim_ids`` and their ancestors
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
        for cid in pred.claim_ids:
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

            - ``claim_ids``: Direct claims jointly implying this prediction
              (copy of ``Prediction.claim_ids``).
            - ``claim_ancestors``: All ancestor claims via transitive
              ``depends_on`` closure, EXCLUDING the direct ``claim_ids``.
            - ``implicit_assumptions``: All assumptions in the full
              derivation chain (same as ``prediction_implicit_assumptions``).

            Returns empty sets for all keys if the prediction does not exist.
        """
        pred = self.predictions.get(pid)
        if pred is None:
            return {"claim_ids": set(), "claim_ancestors": set(), "implicit_assumptions": set()}
        ancestors: set[ClaimId] = set()
        for cid in pred.claim_ids:
            ancestors.update(self.claim_lineage(cid))
        return {
            "claim_ids": pred.claim_ids.copy(),
            "claim_ancestors": ancestors - pred.claim_ids,
            "implicit_assumptions": self.prediction_implicit_assumptions(pid),
        }

    def assumption_support_status(self, aid: AssumptionId) -> dict[str, set]:
        """Compute the full dependency and test coverage of an assumption.

        Answers "what depends on this assumption, and what tests it?"

        Args:
            aid: The assumption ID to analyze.

        Returns:
            dict[str, set]: A dictionary with three keys:

            - ``direct_claims``: Claims that directly reference this
              assumption in their ``assumptions`` set.
            - ``dependent_predictions``: Predictions whose full derivation
              chain includes this assumption (via implicit assumptions).
            - ``tested_by``: Predictions explicitly testing this assumption
              (via ``tests_assumptions``).

            Returns empty sets for all keys if the assumption does not exist.
        """
        assumption = self.assumptions.get(aid)
        if assumption is None:
            return {"direct_claims": set(), "dependent_predictions": set(), "tested_by": set()}
        # Build inverse index once: {AssumptionId: set[PredictionId]}
        implicit_dependents: dict[AssumptionId, set[PredictionId]] = {}
        for pid in self.predictions:
            for dep_aid in self.prediction_implicit_assumptions(pid):
                implicit_dependents.setdefault(dep_aid, set()).add(pid)
        dependent = implicit_dependents.get(aid, set())
        return {
            "direct_claims": assumption.used_in_claims.copy(),
            "dependent_predictions": dependent,
            "tested_by": assumption.tested_by.copy(),
        }

    def claims_depending_on_claim(self, cid: ClaimId) -> set[ClaimId]:
        """Return all claims that transitively depend on this claim.

        Performs a forward traversal from ``cid`` using a reverse
        ``depends_on`` index: "if this claim is wrong, which downstream
        claims are built on it?" The input claim itself is NOT included.

        Args:
            cid: The claim ID to trace forward from.

        Returns:
            set[ClaimId]: All downstream claim IDs that directly or
                transitively depend on ``cid``.
        """
        reverse: dict[ClaimId, set[ClaimId]] = {}
        for other_id, claim in self.claims.items():
            for dep in claim.depends_on:
                reverse.setdefault(dep, set()).add(other_id)
        result: set[ClaimId] = set()
        stack = list(reverse.get(cid, set()))
        while stack:
            current = stack.pop()
            if current in result:
                continue
            result.add(current)
            stack.extend(reverse.get(current, set()))
        return result

    def predictions_depending_on_claim(self, cid: ClaimId) -> set[PredictionId]:
        """Return all predictions whose derivation chain includes this claim.

        Answers "if this claim is retracted, which predictions are now
        suspect?" Considers both direct and downstream claim dependencies.

        Args:
            cid: The claim ID to trace forward from.

        Returns:
            set[PredictionId]: All prediction IDs whose ``claim_ids``
                intersect with ``cid`` or any of its downstream dependents.
        """
        affected_claims = self.claims_depending_on_claim(cid) | {cid}
        return {
            pid for pid, pred in self.predictions.items()
            if pred.claim_ids & affected_claims
        }

    def parameter_impact(self, pid: ParameterId) -> dict[str, set]:
        """Compute the full blast radius of a parameter change.

        Walks the dependency chain: parameter → stale analyses → claims
        covered by those analyses → predictions depending on those claims.
        Also includes claims with ``parameter_constraints`` annotations
        for this parameter and predictions directly linked to stale analyses.

        Args:
            pid: The parameter ID whose impact to compute.

        Returns:
            dict[str, set]: A dictionary with four keys:

            - ``stale_analyses``: Analysis IDs that use this parameter.
            - ``constrained_claims``: Claim IDs with a threshold annotation
              on this parameter.
            - ``affected_claims``: Union of claims covered by stale analyses
              and constrained claims.
            - ``affected_predictions``: All predictions in the downstream
              chain of affected claims, plus predictions directly linked
              to stale analyses.

            Returns empty sets for all keys if the parameter does not exist.
        """
        param = self.parameters.get(pid)
        if param is None:
            return {
                "stale_analyses": set(), "constrained_claims": set(),
                "affected_claims": set(), "affected_predictions": set(),
            }
        stale_analyses = param.used_in_analyses.copy()
        # Claims covered by stale analyses
        affected_claims: set[ClaimId] = set()
        for anid in stale_analyses:
            analysis = self.analyses.get(anid)
            if analysis:
                affected_claims.update(analysis.claims_covered)
        # Claims with explicit threshold constraints on this parameter
        constrained_claims = {
            cid for cid, c in self.claims.items()
            if pid in c.parameter_constraints
        }
        affected_claims.update(constrained_claims)
        # Predictions depending on affected claims (direct + downstream)
        affected_predictions: set[PredictionId] = set()
        for cid in affected_claims:
            affected_predictions.update(self.predictions_depending_on_claim(cid))
        # Also predictions directly linked to stale analyses
        for pred_id, pred in self.predictions.items():
            if pred.analysis in stale_analyses:
                affected_predictions.add(pred_id)
        return {
            "stale_analyses": stale_analyses,
            "constrained_claims": constrained_claims,
            "affected_claims": affected_claims,
            "affected_predictions": affected_predictions,
        }

    # ── Mutations (return new graph) ────────────────────────────────

    def register_claim(self, claim: Claim) -> EpistemicGraph:
        """Register a new claim in the graph.

        Enforces: no duplicate IDs, all referenced assumptions/claims/analyses/
        parameters exist, no dependency cycles in ``depends_on``, and
        bidirectional backlinks are updated on assumptions and analyses.

        The incoming entity is deep-copied so the caller's reference cannot
        mutate the graph's stored copy after registration.

        Args:
            claim: The claim to register. Must have a unique ``id``.

        Returns:
            EpistemicGraph: A new graph instance containing the registered claim.

        Raises:
            DuplicateIdError: If ``claim.id`` already exists.
            BrokenReferenceError: If any referenced ID does not exist.
            CycleError: If ``depends_on`` would create a dependency cycle.
        """
        if claim.id in self.claims:
            raise DuplicateIdError(f"Claim {claim.id} already exists")
        self._check_refs_exist(claim.assumptions, self.assumptions, "assumption")
        self._check_refs_exist(claim.depends_on, self.claims, "claim")
        self._check_refs_exist(claim.analyses, self.analyses, "analysis")
        self._check_refs_exist(set(claim.parameter_constraints.keys()), self.parameters, "parameter")
        self._check_refs_exist(claim.theories, self.theories, "theory")
        self._check_no_cycle_with(claim)

        new = self._copy()
        # Deep-copy the incoming entity so a caller who keeps a reference
        # cannot mutate the graph's stored copy after registration. All
        # register_* methods follow this same pattern.
        new.claims[claim.id] = copy.deepcopy(claim)

        # Maintain bidirectional: assumption.used_in_claims
        for aid in claim.assumptions:
            new.assumptions[aid] = copy.deepcopy(new.assumptions[aid])
            new.assumptions[aid].used_in_claims.add(claim.id)

        # Maintain bidirectional: analysis.claims_covered
        for anid in claim.analyses:
            new.analyses[anid] = copy.deepcopy(new.analyses[anid])
            new.analyses[anid].claims_covered.add(claim.id)

        # Maintain bidirectional: theory.motivates_claims
        for tid in claim.theories:
            new.theories[tid] = copy.deepcopy(new.theories[tid])
            new.theories[tid].motivates_claims.add(claim.id)

        return new

    def register_assumption(self, assumption: Assumption) -> EpistemicGraph:
        """Register a new assumption in the graph.

        Validates that all ``depends_on`` references exist and that no
        cycle would be introduced. Backlinks ``used_in_claims`` and
        ``tested_by`` are intentionally initialized to empty sets —
        they are owned by claim and prediction operations respectively.

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
        stored.used_in_claims = set()
        stored.tested_by = set()
        new.assumptions[assumption.id] = stored
        return new

    def register_prediction(self, prediction: Prediction) -> EpistemicGraph:
        """Register a new prediction in the graph.

        Validates that all referenced claims, assumptions, analysis, and
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
        self._check_refs_exist(prediction.claim_ids, self.claims, "claim")
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
        ``claims_covered`` is a backlink owned by claim operations and
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
        stored.claims_covered = set()
        new.analyses[analysis.id] = stored

        # Maintain bidirectional: parameter.used_in_analyses
        for pid in analysis.uses_parameters:
            new.parameters[pid] = copy.deepcopy(new.parameters[pid])
            new.parameters[pid].used_in_analyses.add(analysis.id)

        return new

    def register_theory(self, theory: Theory) -> EpistemicGraph:
        """Register a new theory in the graph.

        Validates that all ``related_predictions`` IDs exist.
        ``motivates_claims`` is a backlink maintained by claim
        operations and starts empty.

        Args:
            theory: The theory to register. Must have a unique ``id``.

        Returns:
            EpistemicGraph: A new graph instance containing the registered theory.

        Raises:
            DuplicateIdError: If ``theory.id`` already exists.
            BrokenReferenceError: If any referenced ID does not exist.
        """
        if theory.id in self.theories:
            raise DuplicateIdError(f"Theory {theory.id} already exists")
        self._check_refs_exist(theory.related_predictions, self.predictions, "prediction")
        new = self._copy()
        stored = copy.deepcopy(theory)
        stored.motivates_claims = set()
        new.theories[theory.id] = stored
        return new

    def register_independence_group(self, group: IndependenceGroup) -> EpistemicGraph:
        """Register a new independence group in the graph.

        Validates that all ``claim_lineage`` and ``assumption_lineage`` IDs
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
        self._check_refs_exist(group.claim_lineage, self.claims, "claim")
        self._check_refs_exist(group.assumption_lineage, self.assumptions, "assumption")
        new = self._copy()
        stored = copy.deepcopy(group)
        stored.member_predictions = set()
        new.independence_groups[group.id] = stored
        return new

    def register_discovery(self, discovery: Discovery) -> EpistemicGraph:
        """Register a new discovery in the graph.

        Validates that all ``related_claims`` and ``related_predictions``
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
        self._check_refs_exist(discovery.related_claims, self.claims, "claim")
        self._check_refs_exist(discovery.related_predictions, self.predictions, "prediction")
        new = self._copy()
        new.discoveries[discovery.id] = copy.deepcopy(discovery)
        return new

    def register_dead_end(self, dead_end: DeadEnd) -> EpistemicGraph:
        """Register a new dead end record in the graph.

        Validates that all ``related_claims`` and ``related_predictions``
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
        self._check_refs_exist(dead_end.related_claims, self.claims, "claim")
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

    def transition_claim(self, cid: ClaimId, new_status: ClaimStatus) -> EpistemicGraph:
        """Change a claim's lifecycle status.

        Args:
            cid: The claim ID to transition.
            new_status: The new status (ACTIVE, REVISED, or RETRACTED).

        Returns:
            EpistemicGraph: A new graph instance with the updated status.

        Raises:
            BrokenReferenceError: If the claim does not exist.
        """
        if cid not in self.claims:
            raise BrokenReferenceError(f"Claim {cid} does not exist")
        new = self._copy()
        new.claims[cid] = copy.deepcopy(new.claims[cid])
        new.claims[cid].status = new_status
        return new

    def transition_theory(self, tid: TheoryId, new_status: TheoryStatus) -> EpistemicGraph:
        """Change a theory's lifecycle status.

        Args:
            tid: The theory ID to transition.
            new_status: The new status (ACTIVE, REFINED, ABANDONED, or SUPERSEDED).

        Returns:
            EpistemicGraph: A new graph instance with the updated status.

        Raises:
            BrokenReferenceError: If the theory does not exist.
        """
        if tid not in self.theories:
            raise BrokenReferenceError(f"Theory {tid} does not exist")
        new = self._copy()
        new.theories[tid] = copy.deepcopy(new.theories[tid])
        new.theories[tid].status = new_status
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
        uses_parameters, claims_covered) exactly as-is.

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

    def update_claim(self, new_claim: Claim) -> EpistemicGraph:
        """Replace a claim's fields while maintaining all bidirectional links.

        The new claim must have the same ID as an existing claim. Diffs
        old vs new link sets for assumptions and analyses, removing stale
        backlinks and adding new ones. Validates new refs exist and that
        no dependency cycle is introduced.

        Args:
            new_claim: The updated claim. Must have the same ``id`` as
                an existing claim in the graph.

        Returns:
            EpistemicGraph: A new graph instance with the updated claim and
                corrected bidirectional links.

        Raises:
            BrokenReferenceError: If the claim does not exist or if any
                newly referenced ID does not exist.
            CycleError: If the updated ``depends_on`` would create a cycle.
        """
        if new_claim.id not in self.claims:
            raise BrokenReferenceError(f"Claim {new_claim.id} does not exist")
        old = self.claims[new_claim.id]
        self._check_refs_exist(new_claim.assumptions, self.assumptions, "assumption")
        self._check_refs_exist(new_claim.depends_on, self.claims, "claim")
        self._check_refs_exist(new_claim.analyses, self.analyses, "analysis")
        self._check_refs_exist(set(new_claim.parameter_constraints.keys()), self.parameters, "parameter")
        self._check_refs_exist(new_claim.theories, self.theories, "theory")
        self._check_no_cycle_with(new_claim)

        new = self._copy()
        new.claims[new_claim.id] = copy.deepcopy(new_claim)

        # Diff assumption.used_in_claims
        for aid in old.assumptions - new_claim.assumptions:
            new.assumptions[aid] = copy.deepcopy(new.assumptions[aid])
            new.assumptions[aid].used_in_claims.discard(new_claim.id)
        for aid in new_claim.assumptions - old.assumptions:
            new.assumptions[aid] = copy.deepcopy(new.assumptions[aid])
            new.assumptions[aid].used_in_claims.add(new_claim.id)

        # Diff analysis.claims_covered
        for anid in old.analyses - new_claim.analyses:
            new.analyses[anid] = copy.deepcopy(new.analyses[anid])
            new.analyses[anid].claims_covered.discard(new_claim.id)
        for anid in new_claim.analyses - old.analyses:
            new.analyses[anid] = copy.deepcopy(new.analyses[anid])
            new.analyses[anid].claims_covered.add(new_claim.id)

        # Diff theory.motivates_claims
        for tid in old.theories - new_claim.theories:
            new.theories[tid] = copy.deepcopy(new.theories[tid])
            new.theories[tid].motivates_claims.discard(new_claim.id)
        for tid in new_claim.theories - old.theories:
            new.theories[tid] = copy.deepcopy(new.theories[tid])
            new.theories[tid].motivates_claims.add(new_claim.id)

        return new

    def update_assumption(self, new_assumption: Assumption) -> EpistemicGraph:
        """Replace an assumption's fields, preserving owned backlinks.

        ``used_in_claims`` and ``tested_by`` are maintained by claim and
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
        updated.used_in_claims = copy.deepcopy(old.used_in_claims)
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
        self._check_refs_exist(new_prediction.claim_ids, self.claims, "claim")
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

        ``claims_covered`` is a backlink maintained by claim operations and
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
        # Preserve backlink owned by claim operations
        updated.claims_covered = copy.deepcopy(old.claims_covered)
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

    def update_theory(self, new_theory: Theory) -> EpistemicGraph:
        """Replace a theory's fields.

        Validates that all ``related_predictions`` IDs exist.
        ``motivates_claims`` is a backlink maintained by claim operations
        and is preserved from the existing theory.

        Args:
            new_theory: The updated theory. Must have the same ``id``
                as an existing theory.

        Returns:
            EpistemicGraph: A new graph instance with the updated theory.

        Raises:
            BrokenReferenceError: If the theory does not exist or if
                any referenced ID does not exist.
        """
        if new_theory.id not in self.theories:
            raise BrokenReferenceError(f"Theory {new_theory.id} does not exist")
        old = self.theories[new_theory.id]
        self._check_refs_exist(new_theory.related_predictions, self.predictions, "prediction")
        new = self._copy()
        updated = copy.deepcopy(new_theory)
        updated.motivates_claims = copy.deepcopy(old.motivates_claims)
        new.theories[new_theory.id] = updated
        return new

    def update_independence_group(self, new_group: IndependenceGroup) -> EpistemicGraph:
        """Replace an independence group's annotation fields.

        ``member_predictions`` is a backlink maintained by prediction
        operations — preserved from the existing group. Validates
        ``claim_lineage`` and ``assumption_lineage`` refs.

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
        self._check_refs_exist(new_group.claim_lineage, self.claims, "claim")
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

        Validates that all ``related_claims`` and ``related_predictions``
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
        self._check_refs_exist(new_discovery.related_claims, self.claims, "claim")
        self._check_refs_exist(new_discovery.related_predictions, self.predictions, "prediction")
        new = self._copy()
        new.discoveries[new_discovery.id] = copy.deepcopy(new_discovery)
        return new

    def update_dead_end(self, new_dead_end: DeadEnd) -> EpistemicGraph:
        """Replace a dead end's fields.

        Validates that all ``related_claims`` and ``related_predictions``
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
        self._check_refs_exist(new_dead_end.related_claims, self.claims, "claim")
        self._check_refs_exist(new_dead_end.related_predictions, self.predictions, "prediction")
        new = self._copy()
        new.dead_ends[new_dead_end.id] = copy.deepcopy(new_dead_end)
        return new

    # ── Remove mutations — safe deletion with ref checks ──────────

    def remove_prediction(self, pid: PredictionId) -> EpistemicGraph:
        """Remove a prediction from the graph.

        Tears down all backlinks (``Assumption.tested_by``,
        ``IndependenceGroup.member_predictions``) and scrubs soft
        navigational references in theories, dead ends, and discoveries.
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
        # Scrub soft references in theories, dead ends, and discoveries
        for tid, theory in list(new.theories.items()):
            if pid in theory.related_predictions:
                new.theories[tid] = copy.deepcopy(theory)
                new.theories[tid].related_predictions.discard(pid)
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

    def remove_claim(self, cid: ClaimId) -> EpistemicGraph:
        """Remove a claim from the graph.

        Raises if any other claim's ``depends_on`` or any prediction's
        ``claim_ids`` still references this claim. Callers must first
        update or remove all referencing entities.

        On success, tears down backlinks on assumptions and analyses,
        scrubs soft references in theories, dead ends, discoveries,
        and independence group ``claim_lineage`` annotations.

        Args:
            cid: The claim ID to remove.

        Returns:
            EpistemicGraph: A new graph instance without the claim.

        Raises:
            BrokenReferenceError: If the claim does not exist or is still
                referenced by other claims or predictions.
        """
        if cid not in self.claims:
            raise BrokenReferenceError(f"Claim {cid} does not exist")
        blocking_claims = [
            c_id for c_id, c in self.claims.items()
            if cid in c.depends_on and c_id != cid
        ]
        blocking_preds = [
            p_id for p_id, p in self.predictions.items()
            if cid in p.claim_ids
        ]
        if blocking_claims or blocking_preds:
            raise BrokenReferenceError(
                f"Claim {cid} is still referenced by "
                f"claims {blocking_claims} and predictions {blocking_preds}"
            )
        claim = self.claims[cid]
        new = self._copy()
        del new.claims[cid]
        for aid in claim.assumptions:
            if aid in new.assumptions:
                new.assumptions[aid] = copy.deepcopy(new.assumptions[aid])
                new.assumptions[aid].used_in_claims.discard(cid)
        for anid in claim.analyses:
            if anid in new.analyses:
                new.analyses[anid] = copy.deepcopy(new.analyses[anid])
                new.analyses[anid].claims_covered.discard(cid)
        # Tear down bidirectional: theory.motivates_claims
        for tid in claim.theories:
            if tid in new.theories:
                new.theories[tid] = copy.deepcopy(new.theories[tid])
                new.theories[tid].motivates_claims.discard(cid)
        # Scrub soft references in dead ends and discoveries
        for de_id, dead_end in list(new.dead_ends.items()):
            if cid in dead_end.related_claims:
                new.dead_ends[de_id] = copy.deepcopy(dead_end)
                new.dead_ends[de_id].related_claims.discard(cid)
        for disc_id, discovery in list(new.discoveries.items()):
            if cid in discovery.related_claims:
                new.discoveries[disc_id] = copy.deepcopy(discovery)
                new.discoveries[disc_id].related_claims.discard(cid)
        # Scrub soft references in observations
        for oid, obs in list(new.observations.items()):
            if cid in obs.related_claims:
                new.observations[oid] = copy.deepcopy(obs)
                new.observations[oid].related_claims.discard(cid)
        # Scrub claim_lineage annotations in independence groups
        for gid, group in list(new.independence_groups.items()):
            if cid in group.claim_lineage:
                new.independence_groups[gid] = copy.deepcopy(group)
                new.independence_groups[gid].claim_lineage.discard(cid)
        return new

    def remove_assumption(self, aid: AssumptionId) -> EpistemicGraph:
        """Remove an assumption from the graph.

        Raises if any claim, prediction, or other assumption still
        references this assumption. Scrubs ``assumption_lineage``
        annotations in independence groups on success.

        Args:
            aid: The assumption ID to remove.

        Returns:
            EpistemicGraph: A new graph instance without the assumption.

        Raises:
            BrokenReferenceError: If the assumption does not exist or is
                still referenced by claims, predictions, or other assumptions.
        """
        if aid not in self.assumptions:
            raise BrokenReferenceError(f"Assumption {aid} does not exist")
        blocking_claims = [
            c_id for c_id, c in self.claims.items() if aid in c.assumptions
        ]
        blocking_preds = [
            p_id for p_id, p in self.predictions.items()
            if aid in p.tests_assumptions or aid in p.conditional_on
        ]
        blocking_assumptions = [
            a_id for a_id, a in self.assumptions.items()
            if aid in a.depends_on and a_id != aid
        ]
        if blocking_claims or blocking_preds or blocking_assumptions:
            raise BrokenReferenceError(
                f"Assumption {aid} is still referenced by "
                f"claims {blocking_claims}, predictions {blocking_preds}, "
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
        ``parameter_constraints`` annotations on claims.

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
        # Clean up dangling constraint annotations on claims
        for cid, claim in list(new.claims.items()):
            if pid in claim.parameter_constraints:
                new.claims[cid] = copy.deepcopy(claim)
                new.claims[cid].parameter_constraints.pop(pid, None)
        return new

    def remove_analysis(self, anid: AnalysisId) -> EpistemicGraph:
        """Remove an analysis from the graph.

        Raises if any claim's ``analyses`` or any prediction's ``analysis``
        still references this analysis. Tears down
        ``Parameter.used_in_analyses`` backlinks on success.

        Args:
            anid: The analysis ID to remove.

        Returns:
            EpistemicGraph: A new graph instance without the analysis.

        Raises:
            BrokenReferenceError: If the analysis does not exist or is
                still referenced by claims or predictions.
        """
        if anid not in self.analyses:
            raise BrokenReferenceError(f"Analysis {anid} does not exist")
        blocking_claims = [
            cid for cid, c in self.claims.items() if anid in c.analyses
        ]
        blocking_preds = [
            pid for pid, p in self.predictions.items() if p.analysis == anid
        ]
        if blocking_claims or blocking_preds:
            raise BrokenReferenceError(
                f"Analysis {anid} is still referenced by "
                f"claims {blocking_claims} and predictions {blocking_preds}"
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

    def remove_theory(self, tid: TheoryId) -> EpistemicGraph:
        """Remove a theory from the graph.

        Scrubs ``Claim.theories`` references on any claims that were
        motivated by this theory. Does not block on claims — a claim
        can survive without its motivating theory.

        Args:
            tid: The theory ID to remove.

        Returns:
            EpistemicGraph: A new graph instance without the theory.

        Raises:
            BrokenReferenceError: If the theory does not exist.
        """
        if tid not in self.theories:
            raise BrokenReferenceError(f"Theory {tid} does not exist")
        new = self._copy()
        del new.theories[tid]
        # Scrub Claim.theories backlinks
        for cid, claim in list(new.claims.items()):
            if tid in claim.theories:
                new.claims[cid] = copy.deepcopy(claim)
                new.claims[cid].theories.discard(tid)
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

        Validates that all referenced predictions, claims, and assumptions
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
        self._check_refs_exist(observation.related_claims, self.claims, "claim")
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
        self._check_refs_exist(new_observation.related_claims, self.claims, "claim")
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

    def _check_no_cycle_with(self, claim: Claim) -> None:
        """Verify that adding this claim would not create a dependency cycle.

        Walks the ``depends_on`` chain starting from the claim's
        dependencies. If the walk encounters the claim's own ID,
        a cycle would result.

        Args:
            claim: The claim about to be registered or updated.

        Raises:
            CycleError: If adding this claim would create a dependency cycle.
        """
        visited: set[ClaimId] = set()
        stack = list(claim.depends_on)
        while stack:
            current = stack.pop()
            if current == claim.id:
                raise CycleError(
                    f"Adding {claim.id} would create a dependency cycle"
                )
            if current in visited:
                continue
            visited.add(current)
            upstream = self.claims.get(current)
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
            claims=dict(self.claims),
            assumptions=dict(self.assumptions),
            predictions=dict(self.predictions),
            theories=dict(self.theories),
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
