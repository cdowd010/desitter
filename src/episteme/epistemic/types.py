"""Value types and type aliases for the epistemic domain.

No external dependencies. No I/O. Pure data definitions.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import NewType


# ── Typed identifiers ─────────────────────────────────────────────
# NewType gives nominal typing: ClaimId and AnalysisId are both str at
# runtime, but the type checker treats them as distinct types.

ClaimId = NewType("ClaimId", str)
"""Nominal identifier for a :class:`~episteme.epistemic.model.Claim`."""

AssumptionId = NewType("AssumptionId", str)
"""Nominal identifier for an :class:`~episteme.epistemic.model.Assumption`."""

PredictionId = NewType("PredictionId", str)
"""Nominal identifier for a :class:`~episteme.epistemic.model.Prediction`."""

TheoryId = NewType("TheoryId", str)
"""Nominal identifier for a :class:`~episteme.epistemic.model.Theory`."""

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
            detected, e.g. ``"predictions/P-001"`` or ``"payload/claim"``.
        message: A human-readable description of what was found and why
            it matters.
    """
    severity: Severity
    source: str
    message: str


# ── Confidence tiers ──────────────────────────────────────────────

class ConfidenceTier(Enum):
    """How strongly a prediction is constrained.

    FULLY_SPECIFIED: Zero free parameters — pure prediction from theory.
    CONDITIONAL: Valid only if explicitly stated assumptions hold.
    FIT_CHECK: Agreement unsurprising — model was fit to this data, or data
        predates the model (retrodiction). Use evidence_kind to distinguish
        fit vs. retrodiction sub-cases. Cannot be NOVEL_PREDICTION.
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
        The relevant evidence is a direct quantitative value.
        While status is PENDING/NOT_YET_TESTABLE, observed may still be
        absent; once adjudicated (CONFIRMED/STRESSED/REFUTED), observed
        should be present.
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
    """

    CONFIRMED = "CONFIRMED"
    STRESSED = "STRESSED"
    REFUTED = "REFUTED"
    PENDING = "PENDING"
    NOT_YET_TESTABLE = "NOT_YET_TESTABLE"


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


class TheoryStatus(Enum):
    """Lifecycle state of a theory in the research program.

    ACTIVE:
        Currently under active development or evaluation.
    REFINED:
        Updated from an earlier formulation while preserving continuity.
    ABANDONED:
        No longer pursued due to lack of explanatory or predictive value.
    SUPERSEDED:
        Replaced by a better theory/framework.
    """

    ACTIVE = "active"         # currently under investigation
    REFINED = "refined"       # initial formulation has been updated
    ABANDONED = "abandoned"   # no longer pursued
    SUPERSEDED = "superseded" # replaced by a better framework


class DiscoveryStatus(Enum):
    """Progress state of a discovery artifact.

    NEW:
        Recently recorded and not yet integrated into formal structures.
    INTEGRATED:
        Mapped into claims/predictions or otherwise incorporated into the graph.
    ARCHIVED:
        Retained for provenance, with no active integration work.
    """

    NEW = "new"                    # recently found, not yet integrated into the graph
    INTEGRATED = "integrated"      # incorporated as claims or predictions
    ARCHIVED = "archived"          # historical record only


class ClaimStatus(Enum):
    """Lifecycle state of an individual claim.

    ACTIVE:
        Claim is current and considered usable by downstream artifacts.
    REVISED:
        Claim text/semantics changed; dependent entities may require review.
    RETRACTED:
        Claim is invalidated and should not be relied upon.
    """

    ACTIVE = "active"        # normal, in-use
    REVISED = "revised"      # statement updated; downstream may need re-evaluation
    RETRACTED = "retracted"  # found to be wrong; predictions citing it are broken


class ClaimType(Enum):
    """Structural role a claim plays in derivation graphs.

    FOUNDATIONAL:
        A base claim that should not depend on other claims.
    DERIVED:
        A claim whose justification depends on one or more other claims.
    """

    FOUNDATIONAL = "foundational"  # axiomatic starting point; must not depend on other claims
    DERIVED = "derived"            # follows from other claims via depends_on


class ClaimCategory(Enum):
    """High-level semantic category of a claim.

    NUMERICAL:
        Claim makes a quantitative statement and is typically tied to
        analyses, parameters, or thresholds.
    QUALITATIVE:
        Claim is conceptual, structural, or descriptive rather than numeric.
    """

    NUMERICAL = "numerical"    # a quantitative assertion; should have linked analyses
    QUALITATIVE = "qualitative"


class AssumptionType(Enum):
    """Whether an assumption is empirical or methodological in nature.

    EMPIRICAL:
        In principle testable/falsifiable by observation or experiment.
    METHODOLOGICAL:
        A modeling convention, procedural choice, or analysis framing
        assumption.
    """

    EMPIRICAL = "E"        # can in principle be falsified by observation
    METHODOLOGICAL = "M"   # a choice of method or modelling convention


class Criticality(Enum):
    """How load-bearing an assumption is within the epistemic graph.

    LOW:
        Assumption supports a narrow or peripheral part of the project.
    MODERATE:
        Assumption underpins a meaningful portion of the reasoning chain.
    HIGH:
        Assumption is a major structural dependency — many claims and
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
