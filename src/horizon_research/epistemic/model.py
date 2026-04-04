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
    ClaimId,
    ConceptId,
    ConfidenceTier,
    DeadEndId,
    DeadEndStatus,
    DiscoveryId,
    EvidenceKind,
    IndependenceGroupId,
    MeasurementRegime,
    ParameterId,
    PredictionId,
    PredictionStatus,
    TheoryId,
)


@dataclass
class Claim:
    """An atomic, falsifiable assertion.

    depends_on forms a DAG. assumptions and analyses have bidirectional
    links maintained by the EpistemicWeb.
    """
    id: ClaimId
    statement: str
    type: str                                    # "foundational" | "derived"
    scope: str                                   # "global", "domain-specific"
    falsifiability: str
    category: str = "qualitative"                # "numerical" | "qualitative"
    assumptions: set[AssumptionId] = field(default_factory=set)
    depends_on: set[ClaimId] = field(default_factory=set)
    analyses: set[AnalysisId] = field(default_factory=set)
    source: str | None = None                    # doi:..., arxiv:..., url, citation, or "derived from ..."


@dataclass
class Assumption:
    """A premise taken as given."""
    id: AssumptionId
    statement: str
    type: str                                    # "E" (empirical), "M" (methodological)
    scope: str
    used_in_claims: set[ClaimId] = field(default_factory=set)
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
    conditional_on: str | None = None
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
    measurement_regime: str | None = None
    notes: str | None = None


@dataclass
class PairwiseSeparation:
    """Documents why two independence groups are genuinely separate."""
    group_a: IndependenceGroupId
    group_b: IndependenceGroupId
    basis: str


@dataclass
class Analysis:
    """A piece of analytical work whose results feed back into the epistemic web.

    Horizon does not run analyses — the researcher runs them using their
    preferred tools (SageMath, Python, R, Jupyter, etc.) and records the
    result via `horizon record` or the `record_result` MCP tool.

    'path' and 'command' are provenance pointers: they tell the researcher
    (or agent) where the code lives and how to run it. Horizon never invokes
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
    status: str
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
    status: str
    references: list[str] = field(default_factory=list)


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
    source: str | None = None                    # doi:..., arxiv:..., url, or analysis reference


@dataclass
class Concept:
    """A defined term in the project vocabulary."""
    id: ConceptId
    sort_order: int
    term: str
    definition: str
    aliases: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    references: list[str] = field(default_factory=list)
    source: str | None = None                    # primary source for this definition


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


