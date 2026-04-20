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
    AssumptionStatus,
    AssumptionType,
    HypothesisCategory,
    HypothesisId,
    HypothesisStatus,
    HypothesisType,
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
    ObjectiveId,
    ObjectiveKind,
    ObjectiveStatus,
)


@dataclass
class Hypothesis:
    """An atomic, falsifiable assertion in the epistemic graph.

    Hypotheses are the fundamental building blocks of the knowledge graph.
    They form a directed acyclic graph via ``depends_on``, where derived
    hypotheses reference the foundational hypotheses they rest upon.

    The EpistemicGraph maintains bidirectional links between hypotheses and
    their assumptions (``Assumption.used_in_hypotheses``) and analyses
    (``Analysis.hypotheses_covered``). These backlinks are updated
    automatically during registration and updates — callers should
    never modify them directly.

    Attributes:
        id: Unique identifier for this hypothesis (e.g. ``"H-001"``).
        statement: The human-readable text of the assertion.
        type: Structural role — ``FOUNDATIONAL`` (axiomatic base) or
            ``DERIVED`` (depends on other hypotheses). Defaults to
            ``DERIVED``; can be inferred from ``depends_on``.
        scope: Applicability scope, e.g. ``"global"`` or
            ``"domain-specific"``. Defaults to ``"global"``.
        refutation_criteria: Description of what evidence would refute
            this hypothesis. Optional at registration to support early-stage
            or exploratory workflows; should be filled in as the hypothesis
            matures.
        status: Lifecycle state — ``ACTIVE``, ``REVISED``, ``RETRACTED``,
            or ``DEFERRED``.
        category: Whether the hypothesis is ``QUANTITATIVE`` (quantitative) or
            ``QUALITATIVE`` (conceptual/structural).
        assumptions: IDs of assumptions this hypothesis depends on. Bidirectional
            with ``Assumption.used_in_hypotheses``.
        depends_on: IDs of other hypotheses this hypothesis is derived from. Forms a
            DAG enforced by the graph's cycle-detection logic.
        analyses: IDs of analyses linked to this hypothesis. Bidirectional with
            ``Analysis.hypotheses_covered``.
        objectives: IDs of objectives that motivate this hypothesis. Bidirectional
            with ``Objective.motivates_hypotheses``.
        observations: IDs of observations that motivated or are relevant to
            this hypothesis. Soft navigational link — scrubbed on
            observation removal.
        parameter_constraints: Annotation map ``{ParameterId: constraint_str}``
            where the constraint string is human-readable (e.g. ``"< 0.05"``.
            Episteme does not evaluate these — it surfaces them when a
            referenced parameter changes.
        superseded_by: ID of the hypothesis that replaced this one when
            status is ``REVISED`` or ``RETRACTED``. Enables provenance
            chain reconstruction.
        source: Provenance string — DOI, arXiv ID, URL, citation, or
            ``"derived from ..."``.
        notes: Free-form notes for the researcher.
        created: Date the hypothesis was first recorded.
        tags: Free-form labels for filtering, grouping, or cross-cutting
            concerns (e.g. ``"phase:2"``, ``"domain:chemistry"``).
    """
    id: HypothesisId
    statement: str
    type: HypothesisType = HypothesisType.DERIVED
    scope: str = "global"
    refutation_criteria: str | None = None
    status: HypothesisStatus = HypothesisStatus.ACTIVE
    category: HypothesisCategory = HypothesisCategory.QUALITATIVE
    assumptions: set[AssumptionId] = field(default_factory=set)
    depends_on: set[HypothesisId] = field(default_factory=set)
    analyses: set[AnalysisId] = field(default_factory=set)
    objectives: set[ObjectiveId] = field(default_factory=set)
    observations: set[ObservationId] = field(default_factory=set)
    parameter_constraints: dict[ParameterId, str] = field(default_factory=dict)
    superseded_by: HypothesisId | None = None
    source: str | None = None                    # doi:..., arxiv:..., url, citation, or "derived from ..."
    notes: str | None = None
    created: date | None = None
    tags: set[str] = field(default_factory=set)


@dataclass
class Assumption:
    """A premise taken as given within the epistemic graph.

    Assumptions underpin hypotheses and may themselves form presupposition
    chains via ``depends_on``. For example, "the detector is linear"
    depends on "the detector is calibrated." This chain allows
    ``assumption_lineage`` to perform a full transitive closure through
    both hypothesis chains AND assumption chains, ensuring no silent
    dependency is missed.

    Backlinks ``used_in_hypotheses`` and ``tested_by`` are maintained by
    hypothesis and prediction registration operations respectively. They
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
        status: Lifecycle state — ``ACTIVE``, ``QUESTIONED``, ``FALSIFIED``,
            or ``RETIRED``. Defaults to ``ACTIVE``.
        falsifiable_consequence: A description of what evidence would
            falsify this assumption. Required for empirical assumptions
            to pass coverage validation.
        used_in_hypotheses: IDs of hypotheses that reference this assumption.
            Backlink maintained by hypothesis operations — not set by callers.
        depends_on: IDs of other assumptions this one presupposes.
            Forms a DAG enforced by the graph's cycle-detection logic.
        tested_by: IDs of predictions explicitly designed to test this
            assumption. Backlink maintained by prediction operations.
        source: Provenance string — DOI, arXiv ID, URL, or citation.
        notes: Free-form notes for the researcher.
        created: Date the assumption was first recorded.
        tags: Free-form labels for filtering, grouping, or cross-cutting
            concerns.
    """
    id: AssumptionId
    statement: str
    type: AssumptionType
    scope: str = "global"
    criticality: Criticality = Criticality.MODERATE
    status: AssumptionStatus = AssumptionStatus.ACTIVE
    falsifiable_consequence: str | None = None
    used_in_hypotheses: set[HypothesisId] = field(default_factory=set)
    depends_on: set[AssumptionId] = field(default_factory=set)
    tested_by: set[PredictionId] = field(default_factory=set)
    source: str | None = None                    # doi:..., arxiv:..., url, citation, or "derived from ..."
    notes: str | None = None
    created: date | None = None
    tags: set[str] = field(default_factory=set)


@dataclass
class Prediction:
    """A testable consequence of one or more hypotheses.

    Predictions are the empirical interface between the epistemic graph
    and the real world. Each prediction derives from a set of hypotheses
    (``hypothesis_ids``), carries a confidence tier and evidence
    classification, and tracks lifecycle status as evidence accumulates.

    Key semantic distinctions:

    - ``hypothesis_ids``: The hypotheses that jointly imply this prediction (the
      logical derivation chain). Most non-trivial predictions require
      multiple hypotheses. No backlink exists on Hypothesis — the graph validates
      existence only.
    - ``tests_assumptions``: Assumptions this prediction was explicitly
      designed to test — its outcome bears on whether those assumptions
      hold. Bidirectional with ``Assumption.tested_by``.
    - ``conditional_on``: Assumptions this prediction is conditioned on —
      it is valid only if these assumptions hold. Unlike
      ``tests_assumptions``, these are taken as given. A prediction
      cannot both test and condition on the same assumption.
    - ``derivation``: Prose explaining *why* ``hypothesis_ids`` imply this
      prediction (the logical reasoning). Distinct from ``specification``
      (the formula or relationship being tested).

    Attributes:
        id: Unique identifier (e.g. ``"P-001"``).
        observable: What is being measured or observed.
        predicted: The predicted value or outcome (type varies).
        status: Lifecycle state — ``PENDING``, ``CONFIRMED``, ``STRESSED``,
            ``REFUTED``, ``NOT_YET_TESTABLE``, or ``SUPERSEDED``.
            Defaults to ``PENDING``.
        tier: Confidence classification — ``FULLY_SPECIFIED``,
            ``CONDITIONAL``, or ``FIT_CHECK``. Defaults to
            ``FULLY_SPECIFIED``.
        evidence_kind: Temporal/methodological classification —
            ``NOVEL_PREDICTION``, ``RETRODICTION``, or ``FIT_CONSISTENCY``.
            Defaults to ``NOVEL_PREDICTION``.
        measurement_regime: Evidence form — ``MEASURED``, ``BOUND_ONLY``,
            or ``UNMEASURED``. Defaults to ``MEASURED``.
        specification: The formula or relationship being tested (the "what").
        derivation: Why ``hypothesis_ids`` jointly imply this prediction (the "why").
        hypothesis_ids: IDs of hypotheses forming the derivation chain.
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
        refutation_criteria: Description of what evidence would refute this prediction.
        stress_criteria: Description of what evidence would move this
            prediction from CONFIRMED to STRESSED — the threshold for
            tension without full refutation. Together with ``refutation_criteria``,
            this makes the adjudication boundaries explicit and auditable.
        observations: IDs of observations that bear on this prediction.
            Backlink maintained by observation operations — not set by
            callers.
        benchmark_source: Reference to the benchmark data source.
        source: Provenance string — DOI, arXiv ID, URL, or citation.
        notes: Free-form notes for the researcher.
        created: Date the prediction was first recorded.
        supersedes: ID of the prediction this one refines or replaces.
            Enables iteration chains for engineering optimisation workflows.
        predicted_uncertainty: Tolerance or uncertainty on the predicted
            value, same type as ``predicted``. For example,
            ``predicted=1.5, predicted_uncertainty=0.2`` represents
            $1.5 \pm 0.2$.
        observed_uncertainty: Uncertainty on the distilled ``observed``
            value, same type as ``observed``. Complements
            ``predicted_uncertainty`` so the adjudication comparison
            is symmetric: $\hat{y} \pm \delta_\text{pred}$ vs
            $y \pm \delta_\text{obs}$.
        adjudication_rationale: Prose explaining *why* the prediction was
            adjudicated to its current status (CONFIRMED, STRESSED, or
            REFUTED). Distinct from ``refutation_criteria`` (threshold)
            and ``stress_criteria`` (threshold) — this records the actual
            reasoning and evidence that led to the decision.
        tags: Free-form labels for filtering, grouping, or cross-cutting
            concerns.
    """
    id: PredictionId
    observable: str
    predicted: Any                               # the predicted value/outcome
    status: PredictionStatus = PredictionStatus.PENDING
    tier: ConfidenceTier = ConfidenceTier.FULLY_SPECIFIED
    evidence_kind: EvidenceKind = EvidenceKind.NOVEL_PREDICTION
    measurement_regime: MeasurementRegime = MeasurementRegime.MEASURED
    specification: str | None = None             # formula/relationship being tested (the "what")
    derivation: str | None = None                # why hypothesis_ids jointly imply this prediction (the "why")
    hypothesis_ids: set[HypothesisId] = field(default_factory=set)
    tests_assumptions: set[AssumptionId] = field(default_factory=set)
    analysis: AnalysisId | None = None
    independence_group: IndependenceGroupId | None = None
    correlation_tags: set[str] = field(default_factory=set)
    observed: Any = None
    observed_bound: Any = None
    free_params: int = 0
    conditional_on: set[AssumptionId] = field(default_factory=set)
    refutation_criteria: str | None = None
    stress_criteria: str | None = None
    observations: set[ObservationId] = field(default_factory=set)
    benchmark_source: str | None = None
    source: str | None = None                    # doi:..., arxiv:..., url, citation, or "derived from ..."
    notes: str | None = None
    created: date | None = None
    supersedes: PredictionId | None = None
    predicted_uncertainty: Any = None
    observed_uncertainty: Any = None
    adjudication_rationale: str | None = None
    tags: set[str] = field(default_factory=set)


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
        hypothesis_lineage: IDs of hypotheses in the common derivation chain.
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
    hypothesis_lineage: set[HypothesisId] = field(default_factory=set)
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

    ``hypotheses_covered`` is a backlink maintained by hypothesis operations — it
    starts empty on registration and is populated when hypotheses reference
    this analysis.

    Attributes:
        id: Unique identifier (e.g. ``"AN-001"``).
        command: Shell command to invoke the analysis (documentation only).
        path: File path relative to the workspace root.
        hypotheses_covered: IDs of hypotheses linked to this analysis. Backlink
            maintained by hypothesis operations — not set by callers.
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
    hypotheses_covered: set[HypothesisId] = field(default_factory=set)
    uses_parameters: set[ParameterId] = field(default_factory=set)
    notes: str | None = None
    # Result fields — populated by record_analysis_result once the researcher
    # runs the analysis and records the output.
    last_result: Any = None                      # the recorded output value
    last_result_sha: str | None = None           # git SHA of the code at run time
    last_result_date: date | None = None         # date the result was recorded


@dataclass
class Objective:
    """A research objective that motivates and organises hypotheses.

    Objectives unify explanatory frameworks (traditional theories),
    goal-directed research ("achieve X"), and exploratory investigations
    ("understand domain Y") under a single entity. The ``kind`` field
    distinguishes these roles.

    Hypotheses declare which objectives motivate them via
    ``Hypothesis.objectives``, and this entity's ``motivates_hypotheses``
    backlink is maintained automatically by the graph. This makes the
    relationship structural: when an objective is abandoned, the system
    can answer "which hypotheses lose their motivation?"

    ``related_predictions`` and ``related_dead_ends`` / ``related_discoveries``
    are soft navigational links — scrubbed on removal of the referenced entity.

    Attributes:
        id: Unique identifier (e.g. ``"OBJ-001"``).
        title: Human-readable name for the objective.
        kind: The type of objective — ``EXPLANATORY``, ``GOAL``, or
            ``EXPLORATORY``.
        status: Lifecycle state — ``ACTIVE``, ``REFINED``, ``ABANDONED``,
            ``SUPERSEDED``, ``ACHIEVED``, ``INFEASIBLE``, or ``DEFERRED``.
        success_criteria: What counts as achieving this objective.
            Required for ``GOAL`` kind; optional for others.
        summary: Optional prose description of the objective.
        motivates_hypotheses: IDs of hypotheses this objective motivates.
            Backlink maintained by hypothesis operations — not set by callers.
        related_predictions: IDs of predictions this objective generates.
            Soft navigational link — scrubbed on prediction removal.
        related_dead_ends: IDs of dead ends that represent failed
            approaches toward this objective. Soft navigational link.
        related_discoveries: IDs of discoveries made while pursuing
            this objective. Soft navigational link.
        source: Provenance string — DOI, arXiv ID, URL, or citation.
        superseded_by: ID of the objective that replaced this one when
            status is ``SUPERSEDED``. Enables provenance chain
            reconstruction.
        notes: Free-form notes for the researcher.
        created: Date the objective was first recorded.
        tags: Free-form labels for filtering, grouping, or cross-cutting
            concerns.
    """
    id: ObjectiveId
    title: str
    kind: ObjectiveKind
    status: ObjectiveStatus = ObjectiveStatus.ACTIVE
    success_criteria: str | None = None          # what counts as achieved
    summary: str | None = None
    motivates_hypotheses: set[HypothesisId] = field(default_factory=set)
    related_predictions: set[PredictionId] = field(default_factory=set)
    related_dead_ends: set[DeadEndId] = field(default_factory=set)
    related_discoveries: set[DiscoveryId] = field(default_factory=set)
    source: str | None = None                    # doi:..., arxiv:..., url, citation
    superseded_by: ObjectiveId | None = None
    notes: str | None = None
    created: date | None = None
    tags: set[str] = field(default_factory=set)


@dataclass
class Discovery:
    """A significant finding during research.

    Discoveries capture noteworthy results, breakthroughs, or
    observations that may drive new hypotheses or predictions. They
    are leaf entities with soft navigational links to hypotheses and
    predictions that are automatically scrubbed on removal.

    Attributes:
        id: Unique identifier (e.g. ``"D-001"``).
        title: Human-readable name for the discovery.
        date: When the discovery was made or recorded.
        summary: Prose description of what was found.
        impact: Description of the discovery's significance.
        status: Progress state — ``NEW``, ``INTEGRATED``, or ``ARCHIVED``.
        related_hypotheses: IDs of hypotheses connected to this discovery.
            Soft navigational link — scrubbed on hypothesis removal.
        related_predictions: IDs of predictions connected to this discovery.
            Soft navigational link — scrubbed on prediction removal.
        references: List of external reference strings (DOIs, URLs, etc.).
        source: Primary provenance string.
        notes: Free-form notes for the researcher.
        tags: Free-form labels for filtering, grouping, or cross-cutting
            concerns.
    """
    id: DiscoveryId
    title: str
    date: date
    summary: str
    impact: str
    status: DiscoveryStatus = DiscoveryStatus.NEW
    related_hypotheses: set[HypothesisId] = field(default_factory=set)
    related_predictions: set[PredictionId] = field(default_factory=set)
    references: list[str] = field(default_factory=list)
    source: str | None = None                    # doi:..., arxiv:..., url, citation
    notes: str | None = None
    tags: set[str] = field(default_factory=set)


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
        related_hypotheses: IDs of hypotheses connected to this dead end.
            Soft navigational link — scrubbed on hypothesis removal.
        references: List of external reference strings.
        source: Provenance string — DOI, arXiv ID, URL, or analysis reference.
        notes: Free-form notes for the researcher.
        created: Date the dead end was first recorded.
        tags: Free-form labels for filtering, grouping, or cross-cutting
            concerns.
    """
    id: DeadEndId
    title: str
    description: str
    status: DeadEndStatus = DeadEndStatus.ACTIVE
    related_predictions: set[PredictionId] = field(default_factory=set)
    related_hypotheses: set[HypothesisId] = field(default_factory=set)
    references: list[str] = field(default_factory=list)
    source: str | None = None                    # doi:..., arxiv:..., url, or analysis reference
    notes: str | None = None
    created: date | None = None
    tags: set[str] = field(default_factory=set)


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
    prediction or hypothesis is formulated. This supports inductive and
    exploratory workflows where observation precedes hypothesis
    formation, a common pattern in real science that the
    hypothetico-deductive model alone cannot capture.

    Observations can optionally be linked to predictions they bear on:
    ``predictions`` is a forward structural link, and ``Prediction.observations``
    is the auto-maintained backlink.

    An observation without any linked predictions represents an
    exploratory finding that has not yet been connected to the
    reasoning chain. The researcher (or agent) may later formulate
    hypotheses and predictions that reference it.

    Attributes:
        id: Unique identifier (e.g. ``"OBS-001"``).
        description: What was observed, in human-readable prose.
        value: The observed/measured value (numeric, string, or
            structured).
        date: When the observation was made or recorded.
        status: Lifecycle state ``PRELIMINARY``, ``VALIDATED``,
            ``DISPUTED``, or ``RETRACTED``.
        uncertainty: Statistical (random) measurement uncertainty —
            precision. Same type as ``value``. For example,
            ``value=1.23, uncertainty=0.05`` represents
            $1.23 \pm 0.05_\text{stat}$.
        systematic_uncertainty: Systematic measurement uncertainty —
            accuracy/bias. Same type as ``value``. When both are
            present the total error budget is
            $\sigma_\text{total}^2 = \sigma_\text{stat}^2 + \sigma_\text{sys}^2$.
            When only ``uncertainty`` is set it is treated as the total.
        methodology: How the observation was made — experimental
            protocol, instrument, data pipeline, etc.
        predictions: IDs of predictions this observation bears on.
            Bidirectional with ``Prediction.observations``.
        related_hypotheses: IDs of hypotheses this observation is relevant to.
            Soft navigational link scrubbed on hypothesis removal.
        related_assumptions: IDs of assumptions this observation is
            relevant to. Soft navigational link scrubbed on assumption
            removal.
        source: Provenance string DOI, arXiv ID, URL, lab notebook ref.
        notes: Free-form notes for the researcher.
        tags: Free-form labels for filtering, grouping, or cross-cutting
            concerns.
    """
    id: ObservationId
    description: str
    value: Any
    date: date
    status: ObservationStatus = ObservationStatus.PRELIMINARY
    uncertainty: Any = None
    systematic_uncertainty: Any = None
    methodology: str | None = None
    predictions: set[PredictionId] = field(default_factory=set)
    related_hypotheses: set[HypothesisId] = field(default_factory=set)
    related_assumptions: set[AssumptionId] = field(default_factory=set)
    source: str | None = None
    notes: str | None = None
    tags: set[str] = field(default_factory=set)


