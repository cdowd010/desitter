"""Value types and type aliases for the epistemic domain.

No external dependencies. No I/O. Pure data definitions.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import NewType


# ── Typed identifiers ─────────────────────────────────────────────
# NewType gives nominal typing: HypothesisId and AnalysisId are both str at
# runtime, but the type checker treats them as distinct types.

HypothesisId = NewType("HypothesisId", str)
"""Nominal identifier for a :class:`~episteme.epistemic.model.Hypothesis`."""

AssumptionId = NewType("AssumptionId", str)
"""Nominal identifier for an :class:`~episteme.epistemic.model.Assumption`."""

PredictionId = NewType("PredictionId", str)
"""Nominal identifier for a :class:`~episteme.epistemic.model.Prediction`."""

ObjectiveId = NewType("ObjectiveId", str)
"""Nominal identifier for a :class:`~episteme.epistemic.model.Objective`."""

DiscoveryId = NewType("DiscoveryId", str)
"""Nominal identifier for a :class:`~episteme.epistemic.model.Discovery`."""

AnalysisId = NewType("AnalysisId", str)
"""Nominal identifier for an :class:`~episteme.epistemic.model.Analysis`."""

IndependenceGroupId = NewType("IndependenceGroupId", str)
"""Nominal identifier for an :class:`~episteme.epistemic.model.IndependenceGroup`."""

ParameterId = NewType("ParameterId", str)
"""Nominal identifier for a :class:`~episteme.epistemic.model.Parameter`."""

DeadEndId = NewType("DeadEndId", str)
"""Nominal identifier for a :class:`~episteme.epistemic.model.DeadEnd`."""

PairwiseSeparationId = NewType("PairwiseSeparationId", str)
"""Nominal identifier for a :class:`~episteme.epistemic.model.PairwiseSeparation`."""

ObservationId = NewType("ObservationId", str)
"""Nominal identifier for an :class:`~episteme.epistemic.model.Observation`."""



# ── Severity ──────────────────────────────────────────────────────

class Severity(Enum):
    """Severity levels used by findings across validation and checks.

    INFO:
        Non-blocking context that helps explain system state.
    WARNING:
        A potential issue that should be reviewed, but does not invalidate
        the project state by itself.
    CRITICAL:
        A blocking integrity violation that should prevent normal workflows
        until fixed.
    """

    INFO = auto()
    WARNING = auto()
    CRITICAL = auto()


@dataclass
class Finding:
    """A single validation or health-check result.

    Findings are the universal unit of diagnostic output across the entire
    Episteme system: domain invariant validators, payload schema checks,
    health reports, and coverage analyses all produce ``Finding`` instances.

    Attributes:
        severity: The importance level of this finding (INFO, WARNING, or
            CRITICAL). CRITICAL findings block mutations; WARNING and INFO
            are advisory.
        source: A slash-delimited path identifying where the issue was
            detected, e.g. ``"predictions/P-001"`` or ``"payload/hypothesis"``.
        message: A human-readable description of what was found and why
            it matters.
    """
    severity: Severity
    source: str
    message: str


# ── Confidence tiers ──────────────────────────────────────────────

class ConfidenceTier(Enum):
    """How strongly a prediction is constrained.

    FULLY_SPECIFIED: Zero free parameters — pure prediction from hypotheses.
    CONDITIONAL: Valid only if explicitly stated assumptions hold, or
        parameterized with free degrees of freedom (``free_params > 0``).
    FIT_CHECK: Agreement unsurprising — the model was tuned/calibrated
        to match this data. Use ``EvidenceKind`` to distinguish fit
        (``FIT_CONSISTENCY``) from retrodiction (``RETRODICTION``),
        which is a separate and stronger form of evidence.
    """
    FULLY_SPECIFIED = "fully_specified"
    CONDITIONAL = "conditional"
    FIT_CHECK = "fit_check"


# ── Evidence classification ───────────────────────────────────────

class EvidenceKind(Enum):
    """How a prediction relates temporally and methodologically to data.

    NOVEL_PREDICTION:
        Forecast generated before relevant measurements existed.
    RETRODICTION:
        Explanation of already-observed data that was not used to fit
        parameters for this prediction.
    FIT_CONSISTENCY:
        Agreement with data that was part of fitting/calibration and is
        therefore supportive but weak as independent evidence.
    """

    NOVEL_PREDICTION = "novel_prediction"
    RETRODICTION = "retrodiction"
    FIT_CONSISTENCY = "fit_consistency"


class MeasurementRegime(Enum):
    """What kind of empirical evidence form applies to this prediction.

    MEASURED:
        The relevant evidence is a direct value (quantitative or
        categorical). While status is PENDING/NOT_YET_TESTABLE,
        observed may still be absent; once adjudicated
        (CONFIRMED/STRESSED/REFUTED), observed should be present.
    BOUND_ONLY:
        The relevant evidence is an upper/lower bound, not a point estimate.
        While status is PENDING/NOT_YET_TESTABLE, observed_bound may still be
        absent; once adjudicated (CONFIRMED/STRESSED/REFUTED), observed_bound
        should be present.
    UNMEASURED:
        No direct measurement path or bound result is currently available.
    """

    MEASURED = "measured"
    BOUND_ONLY = "bound_only"
    UNMEASURED = "unmeasured"


class PredictionStatus(Enum):
    """Lifecycle state of a prediction as evidence accumulates.

    CONFIRMED:
        Current evidence supports the prediction.
    STRESSED:
        Evidence introduces tension but does not yet decisively refute it.
    REFUTED:
        Evidence contradicts the prediction.
    PENDING:
        Awaiting decisive evidence.
    NOT_YET_TESTABLE:
        No feasible experiment or observation currently exists.
    SUPERSEDED:
        Replaced by a refined or updated prediction via ``supersedes``.
    """

    CONFIRMED = "confirmed"
    STRESSED = "stressed"
    REFUTED = "refuted"
    PENDING = "pending"
    NOT_YET_TESTABLE = "not_yet_testable"
    SUPERSEDED = "superseded"


class DeadEndStatus(Enum):
    """State of a dead-end investigation record.

    ACTIVE:
        The line of investigation is currently tracked as unresolved.
    RESOLVED:
        The dead end has been addressed and closed with rationale.
    ARCHIVED:
        Kept only for historical provenance.
    """

    ACTIVE = "active"
    RESOLVED = "resolved"
    ARCHIVED = "archived"


class ObjectiveKind(Enum):
    """What type of research objective this is.

    EXPLANATORY:
        A theoretical framework that explains phenomena and generates
        hypotheses — the traditional notion of a scientific theory.
    GOAL:
        A concrete target outcome with success criteria, e.g.
        "reduce fuel consumption ≥20%" or "find a treatment for X".
    EXPLORATORY:
        An open-ended investigation to characterise or understand
        a domain, e.g. "map the soil microbiome at site X".
    """

    EXPLANATORY = "explanatory"  # traditional scientific theory
    GOAL = "goal"                # target outcome with success criteria
    EXPLORATORY = "exploratory"  # open-ended investigation


class ObjectiveStatus(Enum):
    """Lifecycle state of an objective in the research program.

    ACTIVE:
        Currently under active development or evaluation.
    REFINED:
        Updated from an earlier formulation while preserving continuity.
    ABANDONED:
        No longer pursued due to lack of explanatory or predictive value.
    SUPERSEDED:
        Replaced by a better objective/framework.
    ACHIEVED:
        Success criteria met (primarily for GOAL objectives).
    INFEASIBLE:
        Determined to be unachievable with current knowledge or
        constraints (primarily for GOAL objectives).
    DEFERRED:
        Paused but not abandoned — may be resumed later.
    """

    ACTIVE = "active"         # currently under investigation
    REFINED = "refined"       # initial formulation has been updated
    ABANDONED = "abandoned"   # no longer pursued
    SUPERSEDED = "superseded" # replaced by a better framework
    ACHIEVED = "achieved"     # success criteria met
    INFEASIBLE = "infeasible" # determined unachievable
    DEFERRED = "deferred"     # paused, not abandoned


class DiscoveryStatus(Enum):
    """Progress state of a discovery artifact.

    NEW:
        Recently recorded and not yet integrated into formal structures.
    INTEGRATED:
        Mapped into hypotheses/predictions or otherwise incorporated into the graph.
    ARCHIVED:
        Retained for provenance, with no active integration work.
    """

    NEW = "new"                    # recently found, not yet integrated into the graph
    INTEGRATED = "integrated"      # incorporated as hypotheses or predictions
    ARCHIVED = "archived"          # historical record only


class HypothesisStatus(Enum):
    """Lifecycle state of an individual hypothesis.

    ACTIVE:
        Hypothesis is current and considered usable by downstream artifacts.
    REVISED:
        Hypothesis text/semantics changed; dependent entities may require review.
    RETRACTED:
        Hypothesis is invalidated and should not be relied upon.
    DEFERRED:
        Investigation paused but not abandoned — may be resumed later.
    """

    ACTIVE = "active"        # normal, in-use
    REVISED = "revised"      # statement updated; downstream may need re-evaluation
    RETRACTED = "retracted"  # found to be wrong; predictions citing it are broken
    DEFERRED = "deferred"    # paused, not abandoned


class HypothesisType(Enum):
    """Structural role a hypothesis plays in derivation graphs.

    FOUNDATIONAL:
        A base hypothesis that should not depend on other hypotheses.
    DERIVED:
        A hypothesis whose justification depends on one or more other hypotheses.
    """

    FOUNDATIONAL = "foundational"  # axiomatic starting point; must not depend on other hypotheses
    DERIVED = "derived"            # follows from other hypotheses via depends_on


class HypothesisCategory(Enum):
    """High-level semantic category of a hypothesis.

    QUANTITATIVE:
        Hypothesis makes a quantitative statement and is typically tied to
        analyses, parameters, or thresholds.
    QUALITATIVE:
        Hypothesis is conceptual, structural, or descriptive rather than numeric.
    """

    QUANTITATIVE = "quantitative"    # a quantitative assertion; should have linked analyses
    QUALITATIVE = "qualitative"


class AssumptionType(Enum):
    """Whether an assumption is empirical or methodological in nature.

    EMPIRICAL:
        In principle testable/falsifiable by observation or experiment.
    METHODOLOGICAL:
        A modeling convention, procedural choice, or analysis framing
        assumption.
    """

    EMPIRICAL = "empirical"        # can in principle be falsified by observation
    METHODOLOGICAL = "methodological"   # a choice of method or modelling convention


class Criticality(Enum):
    """How load-bearing an assumption is within the epistemic graph.

    LOW:
        Assumption supports a narrow or peripheral part of the project.
    MODERATE:
        Assumption underpins a meaningful portion of the reasoning chain.
    HIGH:
        Assumption is a major structural dependency — many hypotheses and
        predictions rest on it.
    LOAD_BEARING:
        Assumption is a single point of failure — if it falls, a large
        fraction of the project's conclusions are invalidated.
    """

    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    LOAD_BEARING = "load_bearing"


class ObservationStatus(Enum):
    """Lifecycle state of an empirical observation.

    PRELIMINARY:
        Initial observation that has not yet been validated or replicated.
    VALIDATED:
        Observation has been checked, replicated, or confirmed by
        independent means.
    DISPUTED:
        The observation's validity or interpretation is contested.
    RETRACTED:
        Observation has been withdrawn due to error or fraud.
    """

    PRELIMINARY = "preliminary"
    VALIDATED = "validated"
    DISPUTED = "disputed"
    RETRACTED = "retracted"
