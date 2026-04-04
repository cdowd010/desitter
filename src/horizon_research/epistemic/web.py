"""The EpistemicWeb: aggregate root for the epistemic domain.

External code NEVER modifies entities directly — it calls methods on the
web, and the web ensures consistency.

Every mutation method returns a NEW web. This gives free undo/redo and
eliminates state corruption.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field

from .model import (
    Analysis,
    Assumption,
    Claim,
    Concept,
    DeadEnd,
    Discovery,
    IndependenceGroup,
    PairwiseSeparation,
    Parameter,
    Prediction,
    Theory,
)
from .types import (
    AnalysisId,
    AssumptionId,
    ClaimId,
    ClaimStatus,
    ConceptId,
    DeadEndId,
    DeadEndStatus,
    DiscoveryId,
    DiscoveryStatus,
    IndependenceGroupId,
    ParameterId,
    PairwiseSeparationId,
    PredictionId,
    PredictionStatus,
    TheoryId,
    TheoryStatus,
)


@dataclass
class EpistemicWeb:
    """Complete epistemic state of a research project.

    All mutations go through methods that enforce invariants and return
    a new web. The old web is left untouched (free rollback).
    """
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
    concepts: dict[ConceptId, Concept] = field(default_factory=dict)
    parameters: dict[ParameterId, Parameter] = field(default_factory=dict)

    # ── Queries ───────────────────────────────────────────────────

    def get_claim(self, cid: ClaimId) -> Claim | None:
        return self.claims.get(cid)

    def get_assumption(self, aid: AssumptionId) -> Assumption | None:
        return self.assumptions.get(aid)

    def get_prediction(self, pid: PredictionId) -> Prediction | None:
        return self.predictions.get(pid)

    def claims_using_assumption(self, aid: AssumptionId) -> set[ClaimId]:
        """All claims that reference this assumption."""
        return {cid for cid, c in self.claims.items() if aid in c.assumptions}

    def claim_lineage(self, cid: ClaimId) -> set[ClaimId]:
        """Transitive closure of depends_on (all ancestors of a claim)."""
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
        """All assumptions reachable through a claim and its ancestors,
        including assumptions presupposed by those assumptions (depends_on)."""
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
        """All assumptions in the full derivation chain of a prediction.

        Includes assumptions on each claim in claim_ids (and their ancestors),
        assumptions presupposed by those assumptions (depends_on chains),
        and assumptions in conditional_on (and their depends_on chains).

        This is the complete set of assumptions the prediction silently rests on.
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
        """What is called into question when a prediction is refuted.

        Returns:
            claim_ids:           the direct claims jointly implying this prediction
            claim_ancestors:     all ancestor claims (transitive depends_on closure)
            implicit_assumptions: all assumptions in the full derivation chain
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
        """What depends on this assumption, directly and transitively.

        Returns:
            direct_claims:          claims that directly reference this assumption
            dependent_predictions:  predictions whose derivation chain includes this assumption
            tested_by:              predictions explicitly testing this assumption
        """
        assumption = self.assumptions.get(aid)
        if assumption is None:
            return {"direct_claims": set(), "dependent_predictions": set(), "tested_by": set()}
        dependent: set[PredictionId] = set()
        for pid in self.predictions:
            if aid in self.prediction_implicit_assumptions(pid):
                dependent.add(pid)
        return {
            "direct_claims": assumption.used_in_claims.copy(),
            "dependent_predictions": dependent,
            "tested_by": assumption.tested_by.copy(),
        }

    def claims_depending_on_claim(self, cid: ClaimId) -> set[ClaimId]:
        """All claims that transitively depend on this claim (forward direction).

        Uses a reverse traversal: builds a reverse depends_on index then
        BFS from cid. Answers "if this claim is wrong, which downstream
        claims are built on it?"
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
        """All predictions whose derivation chain includes this claim.

        Answers "if this claim is retracted, which predictions are now suspect?"
        """
        affected_claims = self.claims_depending_on_claim(cid) | {cid}
        return {
            pid for pid, pred in self.predictions.items()
            if pred.claim_ids & affected_claims
        }

    def parameter_impact(self, pid: ParameterId) -> dict[str, set]:
        """Full blast radius of a parameter change.

        Walks: parameter → stale analyses → claims covered by those analyses
        → predictions depending on those claims. Also includes claims that
        carry a parameter_constraints annotation for this parameter.

        Returns:
            stale_analyses:       analyses that use this parameter
            constrained_claims:   claims with a threshold annotation on this parameter
            affected_claims:      claims covered by stale analyses + constrained claims
            affected_predictions: all predictions in the downstream chain
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

    # ── Mutations (return new web) ────────────────────────────────

    def register_claim(self, claim: Claim) -> EpistemicWeb:
        """Add a claim. Enforces: no duplicates, refs exist, no cycles,
        bidirectional links updated."""
        if claim.id in self.claims:
            raise DuplicateIdError(f"Claim {claim.id} already exists")
        self._check_refs_exist(claim.assumptions, self.assumptions, "assumption")
        self._check_refs_exist(claim.depends_on, self.claims, "claim")
        self._check_refs_exist(claim.analyses, self.analyses, "analysis")
        self._check_refs_exist(set(claim.parameter_constraints.keys()), self.parameters, "parameter")
        self._check_no_cycle_with(claim)

        new = self._copy()
        # Deep-copy the incoming entity so a caller who keeps a reference
        # cannot mutate the web's stored copy after registration. All
        # register_* methods follow this same pattern.
        new.claims[claim.id] = copy.deepcopy(claim)

        # Maintain bidirectional: assumption.used_in_claims
        for aid in claim.assumptions:
            new.assumptions[aid].used_in_claims.add(claim.id)

        # Maintain bidirectional: analysis.claims_covered
        for anid in claim.analyses:
            new.analyses[anid].claims_covered.add(claim.id)

        return new

    def register_assumption(self, assumption: Assumption) -> EpistemicWeb:
        """Add an assumption. Validates depends_on refs exist and no cycles.

        Backlinks (used_in_claims, tested_by) are owned by claim/prediction
        operations and are intentionally initialized empty here.
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

    def register_prediction(self, prediction: Prediction) -> EpistemicWeb:
        """Add a prediction. Enforces: refs exist, bidirectional links updated."""
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
            new.assumptions[aid].tested_by.add(prediction.id)

        # Maintain bidirectional: group.member_predictions
        if prediction.independence_group:
            new.independence_groups[prediction.independence_group].member_predictions.add(
                prediction.id
            )

        return new

    def register_analysis(self, analysis: Analysis) -> EpistemicWeb:
        """Add an analysis reference. Maintains bidirectional uses_parameters link.

        claims_covered is a backlink owned by claim operations and starts empty.
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
            new.parameters[pid].used_in_analyses.add(analysis.id)

        return new

    def register_theory(self, theory: Theory) -> EpistemicWeb:
        """Add a theory. Validates related_claims and related_predictions refs."""
        if theory.id in self.theories:
            raise DuplicateIdError(f"Theory {theory.id} already exists")
        self._check_refs_exist(theory.related_claims, self.claims, "claim")
        self._check_refs_exist(theory.related_predictions, self.predictions, "prediction")
        new = self._copy()
        new.theories[theory.id] = copy.deepcopy(theory)
        return new

    def register_independence_group(self, group: IndependenceGroup) -> EpistemicWeb:
        """Add an independence group. Validates claim_lineage and assumption_lineage refs.

        member_predictions is a backlink owned by prediction operations and
        starts empty.
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

    def register_discovery(self, discovery: Discovery) -> EpistemicWeb:
        """Add a discovery. Validates related_claims and related_predictions refs."""
        if discovery.id in self.discoveries:
            raise DuplicateIdError(f"Discovery {discovery.id} already exists")
        self._check_refs_exist(discovery.related_claims, self.claims, "claim")
        self._check_refs_exist(discovery.related_predictions, self.predictions, "prediction")
        new = self._copy()
        new.discoveries[discovery.id] = copy.deepcopy(discovery)
        return new

    def register_dead_end(self, dead_end: DeadEnd) -> EpistemicWeb:
        """Add a dead end record. Validates related_claims and related_predictions refs."""
        if dead_end.id in self.dead_ends:
            raise DuplicateIdError(f"DeadEnd {dead_end.id} already exists")
        self._check_refs_exist(dead_end.related_claims, self.claims, "claim")
        self._check_refs_exist(dead_end.related_predictions, self.predictions, "prediction")
        new = self._copy()
        new.dead_ends[dead_end.id] = copy.deepcopy(dead_end)
        return new

    def register_concept(self, concept: Concept) -> EpistemicWeb:
        """Add a concept definition."""
        if concept.id in self.concepts:
            raise DuplicateIdError(f"Concept {concept.id} already exists")
        new = self._copy()
        new.concepts[concept.id] = copy.deepcopy(concept)
        return new

    def register_parameter(self, parameter: Parameter) -> EpistemicWeb:
        """Add a parameter constant.

        used_in_analyses is a backlink owned by analysis operations and starts empty.
        """
        if parameter.id in self.parameters:
            raise DuplicateIdError(f"Parameter {parameter.id} already exists")
        new = self._copy()
        stored = copy.deepcopy(parameter)
        stored.used_in_analyses = set()
        new.parameters[parameter.id] = stored
        return new

    def add_pairwise_separation(self, sep: PairwiseSeparation) -> EpistemicWeb:
        """Document why two independence groups are separate."""
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
    ) -> EpistemicWeb:
        """Change a prediction's status."""
        if pid not in self.predictions:
            raise BrokenReferenceError(f"Prediction {pid} does not exist")
        new = self._copy()
        new.predictions[pid].status = new_status
        return new

    def transition_dead_end(
        self,
        did: DeadEndId,
        new_status: DeadEndStatus,
    ) -> EpistemicWeb:
        """Change a dead end's status."""
        if did not in self.dead_ends:
            raise BrokenReferenceError(f"DeadEnd {did} does not exist")
        new = self._copy()
        new.dead_ends[did].status = new_status
        return new

    def transition_claim(self, cid: ClaimId, new_status: ClaimStatus) -> EpistemicWeb:
        """Change a claim's status (ACTIVE → REVISED → RETRACTED)."""
        if cid not in self.claims:
            raise BrokenReferenceError(f"Claim {cid} does not exist")
        new = self._copy()
        new.claims[cid].status = new_status
        return new

    def transition_theory(self, tid: TheoryId, new_status: TheoryStatus) -> EpistemicWeb:
        """Change a theory's status."""
        if tid not in self.theories:
            raise BrokenReferenceError(f"Theory {tid} does not exist")
        new = self._copy()
        new.theories[tid].status = new_status
        return new

    def transition_discovery(self, did: DiscoveryId, new_status: DiscoveryStatus) -> EpistemicWeb:
        """Change a discovery's status."""
        if did not in self.discoveries:
            raise BrokenReferenceError(f"Discovery {did} does not exist")
        new = self._copy()
        new.discoveries[did].status = new_status
        return new

    # ── Update mutations — re-links bidirectional relationships ───

    def update_claim(self, new_claim: Claim) -> EpistemicWeb:
        """Replace a claim's fields, maintaining all bidirectional links.

        The new_claim must have the same ID as the existing claim.
        Diffs old vs new link sets — removes stale backlinks, adds new ones.
        Validates new refs exist and no cycle is introduced.
        """
        if new_claim.id not in self.claims:
            raise BrokenReferenceError(f"Claim {new_claim.id} does not exist")
        old = self.claims[new_claim.id]
        self._check_refs_exist(new_claim.assumptions, self.assumptions, "assumption")
        self._check_refs_exist(new_claim.depends_on, self.claims, "claim")
        self._check_refs_exist(new_claim.analyses, self.analyses, "analysis")
        self._check_refs_exist(set(new_claim.parameter_constraints.keys()), self.parameters, "parameter")
        self._check_no_cycle_with(new_claim)

        new = self._copy()
        new.claims[new_claim.id] = copy.deepcopy(new_claim)

        # Diff assumption.used_in_claims
        for aid in old.assumptions - new_claim.assumptions:
            new.assumptions[aid].used_in_claims.discard(new_claim.id)
        for aid in new_claim.assumptions - old.assumptions:
            new.assumptions[aid].used_in_claims.add(new_claim.id)

        # Diff analysis.claims_covered
        for anid in old.analyses - new_claim.analyses:
            new.analyses[anid].claims_covered.discard(new_claim.id)
        for anid in new_claim.analyses - old.analyses:
            new.analyses[anid].claims_covered.add(new_claim.id)

        return new

    def update_assumption(self, new_assumption: Assumption) -> EpistemicWeb:
        """Replace an assumption's fields.

        used_in_claims and tested_by are maintained by claims/predictions,
        not by the assumption itself — they stay as-is. Only depends_on
        chain changes need validation.
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

    def update_prediction(self, new_prediction: Prediction) -> EpistemicWeb:
        """Replace a prediction's fields, maintaining all bidirectional links."""
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
            new.assumptions[aid].tested_by.discard(new_prediction.id)
        for aid in new_prediction.tests_assumptions - old.tests_assumptions:
            new.assumptions[aid].tested_by.add(new_prediction.id)

        # Diff independence_group.member_predictions
        if old.independence_group != new_prediction.independence_group:
            if old.independence_group and old.independence_group in new.independence_groups:
                new.independence_groups[old.independence_group].member_predictions.discard(new_prediction.id)
            if new_prediction.independence_group and new_prediction.independence_group in new.independence_groups:
                new.independence_groups[new_prediction.independence_group].member_predictions.add(new_prediction.id)

        return new

    def update_parameter(self, new_parameter: Parameter) -> EpistemicWeb:
        """Replace a parameter's fields (value, unit, uncertainty, etc.).

        used_in_analyses is a backlink maintained by analyses — it is
        preserved from the old parameter so callers cannot accidentally
        corrupt the staleness tracking index.
        """
        if new_parameter.id not in self.parameters:
            raise BrokenReferenceError(f"Parameter {new_parameter.id} does not exist")
        old = self.parameters[new_parameter.id]
        new = self._copy()
        updated = copy.deepcopy(new_parameter)
        updated.used_in_analyses = copy.deepcopy(old.used_in_analyses)
        new.parameters[new_parameter.id] = updated
        return new

    def update_analysis(self, new_analysis: Analysis) -> EpistemicWeb:
        """Replace an analysis's fields, maintaining bidirectional links.

        claims_covered is a backlink maintained by claim operations — preserved
        as-is. Diffs uses_parameters and updates parameter.used_in_analyses.
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
                new.parameters[pid].used_in_analyses.discard(new_analysis.id)
        for pid in new_analysis.uses_parameters - old.uses_parameters:
            new.parameters[pid].used_in_analyses.add(new_analysis.id)

        return new

    def update_theory(self, new_theory: Theory) -> EpistemicWeb:
        """Replace a theory's fields. Validates related refs."""
        if new_theory.id not in self.theories:
            raise BrokenReferenceError(f"Theory {new_theory.id} does not exist")
        self._check_refs_exist(new_theory.related_claims, self.claims, "claim")
        self._check_refs_exist(new_theory.related_predictions, self.predictions, "prediction")
        new = self._copy()
        new.theories[new_theory.id] = copy.deepcopy(new_theory)
        return new

    def update_independence_group(self, new_group: IndependenceGroup) -> EpistemicWeb:
        """Replace an independence group's annotation fields.

        member_predictions is a backlink maintained by prediction operations —
        preserved from the existing group. Validates claim_lineage and
        assumption_lineage refs.
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

    def update_pairwise_separation(self, new_sep: PairwiseSeparation) -> EpistemicWeb:
        """Replace a pairwise separation's fields (e.g. updated basis text).
        Validates group refs still exist."""
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

    def update_discovery(self, new_discovery: Discovery) -> EpistemicWeb:
        """Replace a discovery's fields. Validates related refs."""
        if new_discovery.id not in self.discoveries:
            raise BrokenReferenceError(f"Discovery {new_discovery.id} does not exist")
        self._check_refs_exist(new_discovery.related_claims, self.claims, "claim")
        self._check_refs_exist(new_discovery.related_predictions, self.predictions, "prediction")
        new = self._copy()
        new.discoveries[new_discovery.id] = copy.deepcopy(new_discovery)
        return new

    def update_dead_end(self, new_dead_end: DeadEnd) -> EpistemicWeb:
        """Replace a dead end's fields. Validates related refs."""
        if new_dead_end.id not in self.dead_ends:
            raise BrokenReferenceError(f"DeadEnd {new_dead_end.id} does not exist")
        self._check_refs_exist(new_dead_end.related_claims, self.claims, "claim")
        self._check_refs_exist(new_dead_end.related_predictions, self.predictions, "prediction")
        new = self._copy()
        new.dead_ends[new_dead_end.id] = copy.deepcopy(new_dead_end)
        return new

    def update_concept(self, new_concept: Concept) -> EpistemicWeb:
        """Replace a concept's fields."""
        if new_concept.id not in self.concepts:
            raise BrokenReferenceError(f"Concept {new_concept.id} does not exist")
        new = self._copy()
        new.concepts[new_concept.id] = copy.deepcopy(new_concept)
        return new

    # ── Remove mutations — safe deletion with ref checks ──────────

    def remove_prediction(self, pid: PredictionId) -> EpistemicWeb:
        """Remove a prediction. Tears down all backlinks and scrubs soft references.

        No entity hard-blocks prediction removal; Theory, DeadEnd, and Discovery
        hold soft navigational links that are silently scrubbed.
        """
        if pid not in self.predictions:
            raise BrokenReferenceError(f"Prediction {pid} does not exist")
        pred = self.predictions[pid]
        new = self._copy()
        del new.predictions[pid]
        for aid in pred.tests_assumptions:
            if aid in new.assumptions:
                new.assumptions[aid].tested_by.discard(pid)
        if pred.independence_group and pred.independence_group in new.independence_groups:
            new.independence_groups[pred.independence_group].member_predictions.discard(pid)
        # Scrub soft references in theories, dead ends, and discoveries
        for theory in new.theories.values():
            theory.related_predictions.discard(pid)
        for dead_end in new.dead_ends.values():
            dead_end.related_predictions.discard(pid)
        for discovery in new.discoveries.values():
            discovery.related_predictions.discard(pid)
        return new

    def remove_claim(self, cid: ClaimId) -> EpistemicWeb:
        """Remove a claim. Raises if any other claim or prediction references it.

        Tear down the claim's own backlinks on assumptions and analyses.
        Callers must first update or remove all referencing entities.
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
                new.assumptions[aid].used_in_claims.discard(cid)
        for anid in claim.analyses:
            if anid in new.analyses:
                new.analyses[anid].claims_covered.discard(cid)
        # Scrub soft references in theories and dead ends
        for theory in new.theories.values():
            theory.related_claims.discard(cid)
        for dead_end in new.dead_ends.values():
            dead_end.related_claims.discard(cid)
        # Scrub claim_lineage annotations in independence groups
        for group in new.independence_groups.values():
            group.claim_lineage.discard(cid)
        return new

    def remove_assumption(self, aid: AssumptionId) -> EpistemicWeb:
        """Remove an assumption. Raises if any claim, prediction, or other
        assumption references it."""
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
        for group in new.independence_groups.values():
            group.assumption_lineage.discard(aid)
        return new

    def remove_parameter(self, pid: ParameterId) -> EpistemicWeb:
        """Remove a parameter. Raises if any analysis references it.

        Also cleans up dangling parameter_constraints annotations on claims
        so the web stays consistent.
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
        for claim in new.claims.values():
            claim.parameter_constraints.pop(pid, None)
        return new

    def remove_analysis(self, anid: AnalysisId) -> EpistemicWeb:
        """Remove an analysis. Raises if any claim or prediction still references it.

        Tears down parameter.used_in_analyses backlinks.
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
                new.parameters[pid].used_in_analyses.discard(anid)
        return new

    def remove_independence_group(self, gid: IndependenceGroupId) -> EpistemicWeb:
        """Remove an independence group. Raises if any prediction or pairwise
        separation still references it."""
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

    def remove_theory(self, tid: TheoryId) -> EpistemicWeb:
        """Remove a theory. Theories are leaves — nothing references them by ID."""
        if tid not in self.theories:
            raise BrokenReferenceError(f"Theory {tid} does not exist")
        new = self._copy()
        del new.theories[tid]
        return new

    def remove_discovery(self, did: DiscoveryId) -> EpistemicWeb:
        """Remove a discovery. Discoveries are leaves — nothing references them by ID."""
        if did not in self.discoveries:
            raise BrokenReferenceError(f"Discovery {did} does not exist")
        new = self._copy()
        del new.discoveries[did]
        return new

    def remove_dead_end(self, did: DeadEndId) -> EpistemicWeb:
        """Remove a dead end. Dead ends are leaves — nothing references them by ID."""
        if did not in self.dead_ends:
            raise BrokenReferenceError(f"DeadEnd {did} does not exist")
        new = self._copy()
        del new.dead_ends[did]
        return new

    def remove_concept(self, coid: ConceptId) -> EpistemicWeb:
        """Remove a concept. Concepts are leaves — nothing references them by ID."""
        if coid not in self.concepts:
            raise BrokenReferenceError(f"Concept {coid} does not exist")
        new = self._copy()
        del new.concepts[coid]
        return new

    def remove_pairwise_separation(self, sid: PairwiseSeparationId) -> EpistemicWeb:
        """Remove a pairwise separation record."""
        if sid not in self.pairwise_separations:
            raise BrokenReferenceError(f"PairwiseSeparation {sid} does not exist")
        new = self._copy()
        del new.pairwise_separations[sid]
        return new

    # ── Invariant checks ──────────────────────────────────────────

    def _check_refs_exist(self, ids: set, registry: dict, label: str) -> None:
        missing = ids - registry.keys()
        if missing:
            raise BrokenReferenceError(f"Non-existent {label}(s): {missing}")

    def _check_no_cycle_with(self, claim: Claim) -> None:
        """Verify adding this claim doesn't create a cycle in depends_on."""
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
        """Verify adding this assumption doesn't create a cycle in depends_on."""
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

    def _copy(self) -> EpistemicWeb:
        """Deep copy for copy-on-write mutation semantics.

        O(n) cost per mutation where n is total entity count. Acceptable
        for research-scale webs (hundreds to low thousands of entities).
        If this becomes a bottleneck, structural sharing of unchanged
        sub-dicts is the migration path — not a change to make speculatively.
        """
        return copy.deepcopy(self)


# ── Domain exceptions ─────────────────────────────────────────────

class EpistemicError(Exception):
    """Base for all domain errors."""


class DuplicateIdError(EpistemicError):
    pass


class BrokenReferenceError(EpistemicError):
    pass


class CycleError(EpistemicError):
    pass


class InvariantViolation(EpistemicError):
    pass
