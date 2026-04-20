"""Core epistemic entities.

Relationships are ID references, not object references. To traverse
the graph, go through the EpistemicGraph.

Native Python collections throughout: set, list, dict. The graph is
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
    Criticality,
    DeadEndId,
    DeadEndStatus,
    DiscoveryId,
    DiscoveryStatus,
    EvidenceKind,
    IndependenceGroupId,
    MeasurementRegime,
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
class Claim:
    """An atomic, falsifiable assertion in the epistemic graph.

    Claims are the fundamental building blocks of the knowledge graph.
    They form a directed acyclic graph via ``depends_on``, where derived
    claims reference the foundational claims they rest upon.

    The EpistemicGraph maintains bidirectional links between claims and
    their assumptions (``Assumption.used_in_claims``) and analyses
    (``Analysis.claims_covered``). These backlinks are updated
    automatically during registration and updates — callers should
    never modify them directly.

    Attributes:
        id: Unique identifier for this claim (e.g. ``"C-001"``).
        statement: The human-readable text of the assertion.
        type: Structural role — ``FOUNDATIONAL`` (axiomatic base) or
            ``DERIVED`` (depends on other claims).
        scope: Applicability scope, e.g. ``"global"`` or ``"domain-specific"``.
        falsifiability: Description of what evidence would refute this claim.
        status: Lifecycle state — ``ACTIVE``, ``REVISED``, or ``RETRACTED``.
        category: Whether the claim is ``NUMERICAL`` (quantitative) or
            ``QUALITATIVE`` (conceptual/structural).
        assumptions: IDs of assumptions this claim depends on. Bidirectional
            with ``Assumption.used_in_claims``.
        depends_on: IDs of other claims this claim is derived from. Forms a
            DAG enforced by the graph's cycle-detection logic.
        analyses: IDs of analyses linked to this claim. Bidirectional with
            ``Analysis.claims_covered``.
        theories: IDs of theories that motivate this claim. Bidirectional
            with ``Theory.motivates_claims``.
        parameter_constraints: Annotation map ``{ParameterId: constraint_str}``
            where the constraint string is human-readable (e.g. ``"< 0.05"``.
            Episteme does not evaluate these — it surfaces them when a
            referenced parameter changes.
        source: Provenance string — DOI, arXiv ID, URL, citation, or
            ``"derived from ..."``.
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
    theories: set[TheoryId] = field(default_factory=set)
    parameter_constraints: dict[ParameterId, str] = field(default_factory=dict)
    source: str | None = None                    # doi:..., arxiv:..., url, citation, or "derived from ..."


@dataclass
class Assumption:
    """A premise taken as given within the epistemic graph.

    Assumptions underpin claims and may themselves form presupposition
    chains via ``depends_on``. For example, "the detector is linear"
    depends on "the detector is calibrated." This chain allows
    ``assumption_lineage`` to perform a full transitive closure through
    both claim chains AND assumption chains, ensuring no silent
    dependency is missed.

    Backlinks ``used_in_claims`` and ``tested_by`` are maintained by
    claim and prediction registration operations respectively. They
    are intentionally initialized to empty sets on registration.

    Attributes:
        id: Unique identifier for this assumption (e.g. ``"A-001"``).
        statement: The human-readable text of the premise.
        type: Whether the assumption is ``EMPIRICAL`` (testable) or
            ``METHODOLOGICAL`` (a modeling/procedural choice).
        scope: Applicability scope, e.g. ``"global"`` or ``"domain-specific"``.
        criticality: How load-bearing this assumption is. ``LOW``,
            ``MODERATE``, ``HIGH``, or ``LOAD_BEARING``. Defaults to
            ``MODERATE`` — researchers should explicitly upgrade assumptions
            that are single points of failure.
        used_in_claims: IDs of claims that reference this assumption.
            Backlink maintained by claim operations — not set by callers.
        depends_on: IDs of other assumptions this one presupposes.
            Forms a DAG enforced by the graph's cycle-detection logic.
        falsifiable_consequence: A description of what evidence would
            falsify this assumption. Required for empirical assumptions
            to pass coverage validation.
        tested_by: IDs of predictions explicitly designed to test this
            assumption. Backlink maintained by prediction operations.
        source: Provenance string — DOI, arXiv ID, URL, or citation.
        notes: Free-form notes for the researcher.
    """
    id: AssumptionId
    statement: str
    type: AssumptionType
    scope: str
    criticality: Criticality = Criticality.MODERATE
    used_in_claims: set[ClaimId] = field(default_factory=set)
    depends_on: set[AssumptionId] = field(default_factory=set)
    falsifiable_consequence: str | None = None
    tested_by: set[PredictionId] = field(default_factory=set)
    source: str | None = None                    # doi:..., arxiv:..., url, citation, or "derived from ..."
    notes: str | None = None


@dataclass
class Prediction:
    """A testable consequence of one or more claims.

    Predictions are the empirical interface between the epistemic graph
    and the real world. Each prediction derives from a set of claims
    (``claim_ids``), carries a confidence tier and evidence
    classification, and tracks lifecycle status as evidence accumulates.

    Key semantic distinctions:

    - ``claim_ids``: The claims that jointly imply this prediction (the
      logical derivation chain). Most non-trivial predictions require
      multiple claims. No backlink exists on Claim — the graph validates
      existence only.
    - ``tests_assumptions``: Assumptions this prediction was explicitly
      designed to test — its outcome bears on whether those assumptions
      hold. Bidirectional with ``Assumption.tested_by``.
    - ``conditional_on``: Assumptions this prediction is conditioned on —
      it is valid only if these assumptions hold. Unlike
      ``tests_assumptions``, these are taken as given. A prediction
      cannot both test and condition on the same assumption.
    - ``derivation``: Prose explaining *why* ``claim_ids`` imply this
      prediction (the logical reasoning). Distinct from ``specification``
      (the formula or relationship being tested).

    Attributes:
        id: Unique identifier (e.g. ``"P-001"``).
        observable: What is being measured or observed.
        tier: Confidence classification — ``FULLY_SPECIFIED``,
            ``CONDITIONAL``, or ``FIT_CHECK``.
        status: Lifecycle state — ``PENDING``, ``CONFIRMED``, ``STRESSED``,
            ``REFUTED``, or ``NOT_YET_TESTABLE``.
        evidence_kind: Temporal/methodological classification —
            ``NOVEL_PREDICTION``, ``RETRODICTION``, or ``FIT_CONSISTENCY``.
        measurement_regime: Evidence form — ``MEASURED``, ``BOUND_ONLY``,
            or ``UNMEASURED``.
        predicted: The predicted value or outcome (type varies).
        specification: The formula or relationship being tested (the "what").
        derivation: Why ``claim_ids`` jointly imply this prediction (the "why").
        claim_ids: IDs of claims forming the derivation chain.
        tests_assumptions: IDs of assumptions under active test.
        analysis: Optional analysis ID linked to this prediction.
        independence_group: Optional group ID. Bidirectional with
            ``IndependenceGroup.member_predictions``.
        correlation_tags: Free-form tags marking potential correlations.
        observed: The observed value, required once adjudicated with
            ``MEASURED`` regime.
        observed_bound: The observed bound, required once adjudicated with
            ``BOUND_ONLY`` regime.
        free_params: Number of free parameters. Must be 0 for
            ``FULLY_SPECIFIED`` tier.
        conditional_on: IDs of assumptions taken as given for validity.
        falsifier: Description of what evidence would refute this prediction.
        stress_criteria: Description of what evidence would move this
            prediction from CONFIRMED to STRESSED — the threshold for
            tension without full refutation. Together with ``falsifier``,
            this makes the adjudication boundaries explicit and auditable.
        observations: IDs of observations that bear on this prediction.
            Backlink maintained by observation operations — not set by
            callers.
        benchmark_source: Reference to the benchmark data source.
        source: Provenance string — DOI, arXiv ID, URL, or citation.
        notes: Free-form notes for the researcher.
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
    stress_criteria: str | None = None
    observations: set[ObservationId] = field(default_factory=set)
    benchmark_source: str | None = None
    source: str | None = None                    # doi:..., arxiv:..., url, citation, or "derived from ..."
    notes: str | None = None


@dataclass
class IndependenceGroup:
    """A group of predictions sharing a common derivation chain.

    Independence groups allow the system to reason about which
    predictions are genuinely independent pieces of evidence versus
    which share common logical roots. Two groups must be documented
    as separate via a ``PairwiseSeparation`` record once both contain
    member predictions.

    ``member_predictions`` is a backlink maintained by prediction
    registration/update — callers should not set it directly.

    Attributes:
        id: Unique identifier (e.g. ``"IG-001"``).
        label: Human-readable name for the group.
        claim_lineage: IDs of claims in the common derivation chain.
            Caller-maintained annotation — the kernel validates existence
            only, not semantic completeness.
        assumption_lineage: IDs of assumptions in the common chain.
            Caller-maintained annotation — existence-validated only.
        member_predictions: IDs of predictions assigned to this group.
            Backlink maintained by prediction operations.
        measurement_regime: Optional regime shared by all members.
        notes: Free-form notes for the researcher.
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
    """Documents why two independence groups are genuinely separate.

    Required once both referenced groups have at least one member
    prediction. Without this record, validation will report a
    CRITICAL finding for the missing separation basis.

    Attributes:
        id: Unique identifier (e.g. ``"PS-001"``).
        group_a: ID of the first independence group.
        group_b: ID of the second independence group. Must differ
            from ``group_a``.
        basis: Prose explanation of why the two groups provide
            genuinely independent evidence.
    """
    id: PairwiseSeparationId
    group_a: IndependenceGroupId
    group_b: IndependenceGroupId
    basis: str


@dataclass
class Analysis:
    """A piece of analytical work whose results feed back into the epistemic graph.

    Episteme does not run analyses — the researcher runs them using their
    preferred tools (SageMath, Python, R, Jupyter, etc.) and records the
    result via ``ds record`` or the ``record_result`` MCP tool.

    ``path`` and ``command`` are provenance pointers: they tell the researcher
    (or agent) where the code lives and how to run it. Episteme never invokes
    them. The most recently recorded result stores its git SHA directly on the
    analysis, giving a clear provenance chain: path + SHA + recorded value.

    ``uses_parameters`` enables staleness detection: when a Parameter changes,
    ``health_check`` can identify which analyses (and therefore which
    predictions) need to be re-run.

    ``claims_covered`` is a backlink maintained by claim operations — it
    starts empty on registration and is populated when claims reference
    this analysis.

    Attributes:
        id: Unique identifier (e.g. ``"AN-001"``).
        command: Shell command to invoke the analysis (documentation only).
        path: File path relative to the workspace root.
        claims_covered: IDs of claims linked to this analysis. Backlink
            maintained by claim operations — not set by callers.
        uses_parameters: IDs of parameters this analysis depends on.
            Bidirectional with ``Parameter.used_in_analyses``.
        notes: Free-form notes for the researcher.
        last_result: The recorded output value from the most recent run.
        last_result_sha: Git SHA of the analysis code at run time.
        last_result_date: Date when the result was recorded.
    """
    id: AnalysisId
    command: str | None = None                   # how to invoke it (documentation)
    path: str | None = None                      # path to the file, relative to workspace root
    claims_covered: set[ClaimId] = field(default_factory=set)
    uses_parameters: set[ParameterId] = field(default_factory=set)
    notes: str | None = None
    # Result fields — populated by record_analysis_result once the researcher
    # runs the analysis and records the output.
    last_result: Any = None                      # the recorded output value
    last_result_sha: str | None = None           # git SHA of the code at run time
    last_result_date: date | None = None         # date the result was recorded


@dataclass
class Theory:
    """A higher-level explanatory framework being explored.

    A theory motivates and organises claims. Claims declare which theories
    motivate them via ``Claim.theories``, and this entity's
    ``motivates_claims`` backlink is maintained automatically by the graph.
    This makes the relationship structural: when a theory is abandoned,
    the system can answer "which claims lose their theoretical motivation?"

    ``related_predictions`` remains a soft navigational link — predictions
    relate to theories indirectly through claims.

    Attributes:
        id: Unique identifier (e.g. ``"T-001"``).
        title: Human-readable name for the theory.
        status: Lifecycle state — ``ACTIVE``, ``REFINED``, ``ABANDONED``,
            or ``SUPERSEDED``.
        summary: Optional prose description of the theory.
        motivates_claims: IDs of claims this theory motivates. Backlink
            maintained by claim operations — not set by callers.
        related_predictions: IDs of predictions this theory generates.
            Soft navigational link — scrubbed on prediction removal.
        source: Provenance string — DOI, arXiv ID, URL, or citation.
    """
    id: TheoryId
    title: str
    status: TheoryStatus
    summary: str | None = None
    motivates_claims: set[ClaimId] = field(default_factory=set)
    related_predictions: set[PredictionId] = field(default_factory=set)
    source: str | None = None                    # doi:..., arxiv:..., url, citation


@dataclass
class Discovery:
    """A significant finding during research.

    Discoveries capture noteworthy results, breakthroughs, or
    observations that may drive new claims or predictions. They
    are leaf entities with soft navigational links to claims and
    predictions that are automatically scrubbed on removal.

    Attributes:
        id: Unique identifier (e.g. ``"D-001"``).
        title: Human-readable name for the discovery.
        date: When the discovery was made or recorded.
        summary: Prose description of what was found.
        impact: Description of the discovery's significance.
        status: Progress state — ``NEW``, ``INTEGRATED``, or ``ARCHIVED``.
        related_claims: IDs of claims connected to this discovery.
            Soft navigational link — scrubbed on claim removal.
        related_predictions: IDs of predictions connected to this discovery.
            Soft navigational link — scrubbed on prediction removal.
        references: List of external reference strings (DOIs, URLs, etc.).
        source: Primary provenance string.
    """
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

    Records what was tried and why it didn't work. Dead ends are
    valuable negative results that constrain the hypothesis space
    and prevent future researchers from repeating failed approaches.
    They are leaf entities with soft navigational links.

    Attributes:
        id: Unique identifier (e.g. ``"DE-001"``).
        title: Human-readable name for the dead end.
        description: Detailed explanation of what was tried and why
            it failed.
        status: State — ``ACTIVE`` (unresolved), ``RESOLVED`` (addressed),
            or ``ARCHIVED`` (historical only).
        related_predictions: IDs of predictions connected to this dead end.
            Soft navigational link — scrubbed on prediction removal.
        related_claims: IDs of claims connected to this dead end.
            Soft navigational link — scrubbed on claim removal.
        references: List of external reference strings.
        source: Provenance string — DOI, arXiv ID, URL, or analysis reference.
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

    Parameters live in ``project/data/parameters.json`` and are
    available to the researcher when running analyses. They keep
    constants out of scripts and in a single version-controlled
    location.

    ``used_in_analyses`` is a backlink to ``Analysis.uses_parameters``
    maintained automatically by the EpistemicGraph when analyses are
    registered. It enables staleness detection: when this parameter
    changes, ``health_check`` surfaces all analyses (and linked
    predictions) that need to be re-run.

    Attributes:
        id: Unique identifier (e.g. ``"PAR-001"``).
        name: Human-readable name for the parameter.
        value: The parameter value — numeric, string, or structured.
        unit: SI or domain unit string (human-readable), or ``None``.
        uncertainty: Absolute uncertainty, same type as ``value``.
        source: Citation or derivation note.
        used_in_analyses: IDs of analyses that depend on this parameter.
            Backlink maintained by analysis operations — not set by
            callers.
        last_modified: Date when the parameter value was last changed.
            Used by ``check_stale`` to identify analyses whose results
            predate the most recent parameter change.
        notes: Free-form notes for the researcher.
    """
    id: ParameterId
    name: str
    value: Any                          # numeric, string, or structured
    unit: str | None = None             # SI or domain unit, human-readable
    uncertainty: Any = None             # absolute uncertainty, same type as value
    source: str | None = None           # citation or derivation note
    used_in_analyses: set[AnalysisId] = field(default_factory=set)
    last_modified: date | None = None   # when the value was last changed
    notes: str | None = None


@dataclass
class Observation:
    """A recorded empirical observation or measurement.

    Observations capture raw empirical data that may exist before any
    prediction or claim is formulated. This supports inductive and
    exploratory workflows where observation precedes hypothesis
    formation, a common pattern in real science that the
    hypothetico-deductive model alone cannot capture.

    Observations can optionally be linked to predictions they bear on:
    ``predictions`` is a forward structural link, and ``Prediction.observations``
    is the auto-maintained backlink.

    An observation without any linked predictions represents an
    exploratory finding that has not yet been connected to the
    reasoning chain. The researcher (or agent) may later formulate
    claims and predictions that reference it.

    Attributes:
        id: Unique identifier (e.g. ``"OBS-001"``).
        description: What was observed, in human-readable prose.
        value: The observed/measured value (numeric, string, or
            structured).
        date: When the observation was made or recorded.
        status: Lifecycle state ``PRELIMINARY``, ``VALIDATED``,
            ``DISPUTED``, or ``RETRACTED``.
        methodology: How the observation was made — experimental
            protocol, instrument, data pipeline, etc.
        predictions: IDs of predictions this observation bears on.
            Bidirectional with ``Prediction.observations``.
        related_claims: IDs of claims this observation is relevant to.
            Soft navigational link scrubbed on claim removal.
        related_assumptions: IDs of assumptions this observation is
            relevant to. Soft navigational link scrubbed on assumption
            removal.
        source: Provenance string DOI, arXiv ID, URL, lab notebook ref.
        notes: Free-form notes for the researcher.
    """
    id: ObservationId
    description: str
    value: Any
    date: date
    status: ObservationStatus
    methodology: str | None = None
    predictions: set[PredictionId] = field(default_factory=set)
    related_claims: set[ClaimId] = field(default_factory=set)
    related_assumptions: set[AssumptionId] = field(default_factory=set)
    source: str | None = None
    notes: str | None = None


