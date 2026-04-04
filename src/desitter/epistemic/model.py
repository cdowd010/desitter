"""Core epistemic entities.

Relationships are ID references, not object references. To traverse
the graph, go through the EpistemicWeb.

Native Python collections throughout: set, list, dict. The web is
the encapsulation boundary, not the type system.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from .types import (
    AnalysisId,
    AssumptionId,
    AssumptionType,
    ClaimCategory,
    ClaimId,
    ClaimStatus,
    ClaimType,
    ConfidenceTier,
    DeadEndId,
    DeadEndStatus,
    DiscoveryId,
    DiscoveryStatus,
    EvidenceKind,
    IndependenceGroupId,
    MeasurementRegime,
    ParameterId,
    PairwiseSeparationId,
    PredictionId,
    PredictionStatus,
    TheoryId,
    TheoryStatus,
)


@dataclass
class Claim:
    """An atomic, falsifiable assertion.

    depends_on forms a DAG. assumptions and analyses have bidirectional
    links maintained by the EpistemicWeb.

    'parameter_constraints' is an annotation map: {ParameterId: constraint_str}.
    The constraint string is human-readable ("< 0.05", "> 3.0", "in [0.1, 10]").
    deSitter does not evaluate constraints — it surfaces them when a referenced
    parameter changes, so the researcher knows to re-check this claim.
    """
    id: ClaimId
    statement: str
    type: ClaimType
    scope: str                                   # "global", "domain-specific"
    falsifiability: str
    status: ClaimStatus = ClaimStatus.ACTIVE
    category: ClaimCategory = ClaimCategory.QUALITATIVE
    assumptions: set[AssumptionId] = field(default_factory=set)
    depends_on: set[ClaimId] = field(default_factory=set)
    analyses: set[AnalysisId] = field(default_factory=set)
    parameter_constraints: dict[ParameterId, str] = field(default_factory=dict)
    source: str | None = None                    # doi:..., arxiv:..., url, citation, or "derived from ..."


@dataclass
class Assumption:
    """A premise taken as given.

    'depends_on' captures presupposition: "the detector is linear" depends on
    "the detector is calibrated." This lets assumption_lineage do a full
    transitive closure through both claim chains AND assumption chains, so
    no silent dependency is missed.
    """
    id: AssumptionId
    statement: str
    type: AssumptionType
    scope: str
    used_in_claims: set[ClaimId] = field(default_factory=set)
    depends_on: set[AssumptionId] = field(default_factory=set)
    falsifiable_consequence: str | None = None
    tested_by: set[PredictionId] = field(default_factory=set)
    source: str | None = None                    # doi:..., arxiv:..., url, citation, or "derived from ..."
    notes: str | None = None


@dataclass
class Prediction:
    """A testable consequence of one or more claims.

    'claim_ids' is the set of claims that jointly imply this prediction —
    the logical derivation chain. Most non-trivial predictions require
    multiple claims together. Bidirectional maintenance is one-way only:
    the web validates all claim_ids exist; no backlink on Claim.

    'tests_assumptions' is the set of assumptions this prediction was
    explicitly designed to test — i.e., its outcome bears on whether
    those assumptions hold. Bidirectional with Assumption.tested_by.

    'derivation' is the prose explanation of why claim_ids → this
    prediction. Distinct from 'specification' (the formula being tested).

    'conditional_on' is the set of assumptions this prediction is explicitly
    conditioned on — i.e., "this prediction holds only if these assumptions
    hold." Unlike tests_assumptions (which marks assumptions under active
    test), conditional_on marks assumptions that are taken as given for
    this prediction to be valid. The web validates all IDs exist.
    """
    id: PredictionId
    observable: str
    tier: ConfidenceTier
    status: PredictionStatus
    evidence_kind: EvidenceKind
    measurement_regime: MeasurementRegime
    predicted: Any                               # the predicted value/outcome
    specification: str | None = None             # formula/relationship being tested (the "what")
    derivation: str | None = None                # why claim_ids jointly imply this prediction (the "why")
    claim_ids: set[ClaimId] = field(default_factory=set)
    tests_assumptions: set[AssumptionId] = field(default_factory=set)
    analysis: AnalysisId | None = None
    independence_group: IndependenceGroupId | None = None
    correlation_tags: set[str] = field(default_factory=set)
    observed: Any = None
    observed_bound: Any = None
    free_params: int = 0
    conditional_on: set[AssumptionId] = field(default_factory=set)
    falsifier: str | None = None
    benchmark_source: str | None = None
    source: str | None = None                    # doi:..., arxiv:..., url, citation, or "derived from ..."
    notes: str | None = None


@dataclass
class IndependenceGroup:
    """Predictions sharing a common derivation chain.

    member_predictions is bidirectional with Prediction.independence_group.
    """
    id: IndependenceGroupId
    label: str
    claim_lineage: set[ClaimId] = field(default_factory=set)
    assumption_lineage: set[AssumptionId] = field(default_factory=set)
    member_predictions: set[PredictionId] = field(default_factory=set)
    measurement_regime: MeasurementRegime | None = None
    notes: str | None = None


@dataclass
class PairwiseSeparation:
    """Documents why two independence groups are genuinely separate."""
    id: PairwiseSeparationId
    group_a: IndependenceGroupId
    group_b: IndependenceGroupId
    basis: str


@dataclass
class Analysis:
    """A piece of analytical work whose results feed back into the epistemic web.

    deSitter does not run analyses — the researcher runs them using their
    preferred tools (SageMath, Python, R, Jupyter, etc.) and records the
    result via `ds record` or the `record_result` MCP tool.

    'path' and 'command' are provenance pointers: they tell the researcher
    (or agent) where the code lives and how to run it. deSitter never invokes
    them. The git SHA at record time is captured on the AnalysisResult, giving
    a complete immutable provenance chain: path + SHA + recorded value.

    'uses_parameters' enables staleness detection: when a Parameter changes,
    health_check can identify which analyses (and therefore which predictions)
    need to be re-run. Bidirectional with Parameter.used_in_analyses.
    """
    id: AnalysisId
    command: str | None = None                   # how to invoke it (documentation)
    path: str | None = None                      # path to the file, relative to workspace root
    claims_covered: set[ClaimId] = field(default_factory=set)
    uses_parameters: set[ParameterId] = field(default_factory=set)
    notes: str | None = None


@dataclass
class Theory:
    """A higher-level explanatory framework being explored.

    A theory motivates and organises claims. Claims are the atomic
    assertions the theory rests on; predictions are what the theory
    predicts that could be tested.
    """
    id: TheoryId
    title: str
    status: TheoryStatus
    summary: str | None = None
    related_claims: set[ClaimId] = field(default_factory=set)
    related_predictions: set[PredictionId] = field(default_factory=set)
    source: str | None = None                    # doi:..., arxiv:..., url, citation


@dataclass
class Discovery:
    """A significant finding during research."""
    id: DiscoveryId
    title: str
    date: date
    summary: str
    impact: str
    status: DiscoveryStatus
    related_claims: set[ClaimId] = field(default_factory=set)
    related_predictions: set[PredictionId] = field(default_factory=set)
    references: list[str] = field(default_factory=list)
    source: str | None = None                    # doi:..., arxiv:..., url, citation


@dataclass
class DeadEnd:
    """A known dead end or abandoned direction.

    Records what was tried and why it didn't work. Valuable negative
    results that constrain the hypothesis space.
    """
    id: DeadEndId
    title: str
    description: str
    status: DeadEndStatus
    related_predictions: set[PredictionId] = field(default_factory=set)
    related_claims: set[ClaimId] = field(default_factory=set)
    references: list[str] = field(default_factory=list)
    source: str | None = None                    # doi:..., arxiv:..., url, or analysis reference


@dataclass
class Parameter:
    """A physical or mathematical constant referenced by analyses.

    Parameters live in project/data/parameters.json and are available
    to the researcher when running analyses. They keep constants out of
    scripts and in a single version-controlled location.

    'used_in_analyses' is the bidirectional backlink to Analysis.uses_parameters.
    The EpistemicWeb maintains this automatically when analyses are registered.
    It enables staleness detection: when this parameter changes, health_check
    surfaces all analyses (and linked predictions) that need to be re-run.
    """
    id: ParameterId
    name: str
    value: Any                          # numeric, string, or structured
    unit: str | None = None             # SI or domain unit, human-readable
    uncertainty: Any = None             # absolute uncertainty, same type as value
    source: str | None = None           # citation or derivation note
    used_in_analyses: set[AnalysisId] = field(default_factory=set)
    notes: str | None = None


