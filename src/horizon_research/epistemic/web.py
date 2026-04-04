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
    ConceptId,
    DeadEndId,
    DeadEndStatus,
    DiscoveryId,
    Finding,
    IndependenceGroupId,
    ParameterId,
    PairwiseSeparationId,
    PredictionId,
    PredictionStatus,
    Severity,
    TheoryId,
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

    # ── Mutations (return new web) ────────────────────────────────

    def register_claim(self, claim: Claim) -> EpistemicWeb:
        """Add a claim. Enforces: no duplicates, refs exist, no cycles,
        bidirectional links updated."""
        if claim.id in self.claims:
            raise DuplicateIdError(f"Claim {claim.id} already exists")
        self._check_refs_exist(claim.assumptions, self.assumptions, "assumption")
        self._check_refs_exist(claim.depends_on, self.claims, "claim")
        self._check_refs_exist(claim.analyses, self.analyses, "analysis")
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
        """Add an assumption. Validates depends_on refs exist and no cycles."""
        if assumption.id in self.assumptions:
            raise DuplicateIdError(f"Assumption {assumption.id} already exists")
        self._check_refs_exist(assumption.depends_on, self.assumptions, "assumption")
        self._check_no_assumption_cycle_with(assumption)
        new = self._copy()
        new.assumptions[assumption.id] = copy.deepcopy(assumption)
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
        """Add an analysis reference. Maintains bidirectional uses_parameters link."""
        if analysis.id in self.analyses:
            raise DuplicateIdError(f"Analysis {analysis.id} already exists")
        self._check_refs_exist(analysis.uses_parameters, self.parameters, "parameter")

        new = self._copy()
        new.analyses[analysis.id] = copy.deepcopy(analysis)

        # Maintain bidirectional: parameter.used_in_analyses
        for pid in analysis.uses_parameters:
            new.parameters[pid].used_in_analyses.add(analysis.id)

        return new

    def register_theory(self, theory: Theory) -> EpistemicWeb:
        """Add a theory."""
        if theory.id in self.theories:
            raise DuplicateIdError(f"Theory {theory.id} already exists")
        new = self._copy()
        new.theories[theory.id] = theory
        return new

    def register_independence_group(self, group: IndependenceGroup) -> EpistemicWeb:
        """Add an independence group."""
        if group.id in self.independence_groups:
            raise DuplicateIdError(f"Independence group {group.id} already exists")
        new = self._copy()
        new.independence_groups[group.id] = group
        return new

    def register_discovery(self, discovery: Discovery) -> EpistemicWeb:
        """Add a discovery."""
        if discovery.id in self.discoveries:
            raise DuplicateIdError(f"Discovery {discovery.id} already exists")
        new = self._copy()
        new.discoveries[discovery.id] = discovery
        return new

    def register_dead_end(self, dead_end: DeadEnd) -> EpistemicWeb:
        """Add a dead end record."""
        if dead_end.id in self.dead_ends:
            raise DuplicateIdError(f"DeadEnd {dead_end.id} already exists")
        new = self._copy()
        new.dead_ends[dead_end.id] = dead_end
        return new

    def register_concept(self, concept: Concept) -> EpistemicWeb:
        """Add a concept definition."""
        if concept.id in self.concepts:
            raise DuplicateIdError(f"Concept {concept.id} already exists")
        new = self._copy()
        new.concepts[concept.id] = concept
        return new

    def register_parameter(self, parameter: Parameter) -> EpistemicWeb:
        """Add a parameter constant."""
        if parameter.id in self.parameters:
            raise DuplicateIdError(f"Parameter {parameter.id} already exists")
        new = self._copy()
        new.parameters[parameter.id] = parameter
        return new

    def add_pairwise_separation(self, sep: PairwiseSeparation) -> EpistemicWeb:
        """Document why two independence groups are separate."""
        if sep.id in self.pairwise_separations:
            raise DuplicateIdError(f"PairwiseSeparation {sep.id} already exists")
        if sep.group_a not in self.independence_groups:
            raise BrokenReferenceError(f"Group {sep.group_a} does not exist")
        if sep.group_b not in self.independence_groups:
            raise BrokenReferenceError(f"Group {sep.group_b} does not exist")
        new = self._copy()
        new.pairwise_separations[sep.id] = sep
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
