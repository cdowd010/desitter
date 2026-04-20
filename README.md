# Episteme

*Versioned, invariant-enforced tracking for the epistemic structure of research.*

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![License: Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Status: Early Development](https://img.shields.io/badge/status-early%20development-orange.svg)](TRACKER.md)

> **Early development.** The epistemic kernel is implemented and tested.
> The control plane, adapters, and interface layers are in progress.
> See [TRACKER.md](TRACKER.md) for current build status.

---

## What It Is

The scientific method has a structure: you make **hypotheses**, ground them in
**assumptions**, derive **predictions**, run **analyses** to test those
predictions, record **observations**, and evaluate what the evidence shows.
That structure exists in every research project, but it almost never gets
tracked. It lives in documents, email threads, and researcher memory, and it
breaks silently.

A refuted prediction does not update the hypotheses that depend on it. A
revised assumption does not propagate to its consequences. Predictions
accumulate that still cite retracted hypotheses. Assumptions go untested
because nobody can see they are load-bearing. Six months later, nobody can
trace why a conclusion was drawn or whether the underlying support was ever
intact. There is no standard tooling for this. Version control, lab notebooks,
and project management software all sidestep it.

Episteme fills that gap. It is a versioned, graph-structured registry of your
**epistemic chain**: every hypothesis, assumption, prediction, observation,
analysis, parameter, objective, discovery, and dead end. Hard invariants keep
the graph consistent as research evolves. Validators surface structural facts
about the graph: missing links, untested assumptions, stale analyses,
compromised observation bases, supersession inconsistencies, and more.

Episteme is an **audit scaffold**, not a reasoning engine. The researcher (or
an AI agent) decides what to do about what it finds. But it makes the
reasoning visible and keeps it honest.

---

## Core Capabilities

- **Register** hypotheses, assumptions, predictions, observations, analyses,
  parameters, objectives, discoveries, independence groups, pairwise
  separations, and dead ends in a typed, versioned graph
- **Enforce** referential integrity, DAG acyclicity, bidirectional backlinks,
  tier constraints, and field-level consistency at write time
- **Validate** the full epistemic graph on demand against 31 semantic
  invariant validators
- **Track evidence** through prediction tiers (`FULLY_SPECIFIED`,
  `CONDITIONAL`, `FIT_CHECK`) with explicit independence-group accounting
  and three orthogonal classification axes (tier, evidence kind, measurement
  regime)
- **Detect staleness** when a parameter changes and propagate impact through
  analyses, hypotheses, and predictions
- **Trace blast radius** with typed query results: `refutation_impact`,
  `assumption_support_status`, `parameter_impact`
- **Lifecycle management** with guarded status transitions for seven entity
  types, each with an explicit transition table
- **Supersession chains** across predictions, hypotheses, and objectives with
  automatic predecessor transition and cycle detection

Episteme never executes analyses. Researchers run their own tools (Python, R,
SageMath, Jupyter) and record outcomes. Episteme records provenance, enforces
structure, and tracks what changed.

---

## The Epistemic Graph

The `EpistemicGraph` is the aggregate root. All mutations go through it and
return a new immutable graph instance (copy-on-write). The old instance is
never modified, giving free undo/redo semantics.

### Entities (11 types)

| Entity | Role |
|--------|------|
| **Hypothesis** | Atomic, falsifiable assertion. Forms a DAG via `depends_on`. Categorized as `FOUNDATIONAL` or `DERIVED`, `QUANTITATIVE` or `QUALITATIVE`. |
| **Assumption** | Premise taken as given. `EMPIRICAL` (testable) or `METHODOLOGICAL` (procedural). Chains via `depends_on`. Criticality: `LOW` / `MODERATE` / `HIGH` / `LOAD_BEARING`. |
| **Prediction** | Testable consequence of hypotheses. Three orthogonal axes: confidence tier, evidence kind, measurement regime. Supports `predicted_uncertainty` / `observed_uncertainty` for symmetric comparison. |
| **Observation** | Raw empirical data. Supports inductive workflows where data precedes hypotheses. Tracks `uncertainty` (statistical) and `systematic_uncertainty` separately. |
| **Analysis** | Provenance pointer to researcher-run code. Tracks `last_result`, `last_result_sha`, `last_result_date` for staleness detection. |
| **Parameter** | Physical or mathematical constant. `used_in_analyses` backlink enables staleness propagation. |
| **Objective** | Research motivation. `EXPLANATORY` (theory), `GOAL` (target outcome), or `EXPLORATORY` (open investigation). Hub entity linking to hypotheses, predictions, observations, discoveries, and dead ends. |
| **Discovery** | Significant finding. Soft links to hypotheses and predictions. |
| **Dead End** | Failed approach. Negative results that constrain the hypothesis space. |
| **Independence Group** | Predictions sharing a common derivation chain. |
| **Pairwise Separation** | Documents why two independence groups provide genuinely separate evidence. |

### Lifecycle States and Transitions

Each entity type with a status field has an explicit transition table. Terminal
states cannot be exited. Transitions are enforced at mutation time.

| Entity | States | Terminal |
|--------|--------|----------|
| Hypothesis | `ACTIVE`, `REVISED`, `DEFERRED`, `RETRACTED` | `RETRACTED` |
| Assumption | `ACTIVE`, `QUESTIONED`, `FALSIFIED`, `RETIRED` | `FALSIFIED`, `RETIRED` |
| Prediction | `PENDING`, `CONFIRMED`, `STRESSED`, `REFUTED`, `NOT_YET_TESTABLE`, `SUPERSEDED` | `SUPERSEDED` |
| Observation | `PRELIMINARY`, `VALIDATED`, `DISPUTED`, `RETRACTED` | `RETRACTED` |
| Objective | `ACTIVE`, `REFINED`, `DEFERRED`, `ABANDONED`, `SUPERSEDED`, `ACHIEVED`, `INFEASIBLE` | `ABANDONED`, `SUPERSEDED`, `ACHIEVED`, `INFEASIBLE` |
| Discovery | `NEW`, `INTEGRATED`, `ARCHIVED` | `ARCHIVED` |
| Dead End | `ACTIVE`, `RESOLVED`, `ARCHIVED` | `ARCHIVED` |

### Bidirectional Links

The graph automatically maintains backlinks when entities are registered,
updated, or removed:

- `Hypothesis.assumptions` <-> `Assumption.used_in_hypotheses`
- `Hypothesis.analyses` <-> `Analysis.hypotheses_covered`
- `Hypothesis.objectives` <-> `Objective.motivates_hypotheses`
- `Prediction.tests_assumptions` <-> `Assumption.tested_by`
- `Prediction.independence_group` <-> `IndependenceGroup.member_predictions`
- `Observation.predictions` <-> `Prediction.observations`
- `Analysis.uses_parameters` <-> `Parameter.used_in_analyses`

Soft navigational links (on objectives, discoveries, dead ends, hypotheses,
observations) are scrubbed automatically on entity removal.

---

## Validators (31)

Semantic invariants are checked on demand via `validate_all(graph)`. Each
validator is a pure function: `(EpistemicGraphPort) -> list[Finding]`.

Findings have three severity levels:
- **CRITICAL**: Blocking integrity violation.
- **WARNING**: Issue that should be reviewed.
- **INFO**: Non-blocking context or workflow nudge.

| # | Validator | Severity | What It Checks |
|---|-----------|----------|----------------|
| 1 | `validate_retracted_hypothesis_citations` | CRITICAL/INFO | Predictions or hypotheses citing retracted hypotheses |
| 2 | `validate_tests_conditional_overlap` | CRITICAL | Predictions that both test and condition on the same assumption |
| 3 | `validate_tier_constraints` | CRITICAL/WARNING | Tier/regime consistency (free params, observed values, conditionality) |
| 4 | `validate_evidence_consistency` | WARNING | FIT_CHECK paired with contradictory evidence kinds |
| 5 | `validate_independence_semantics` | CRITICAL | Group back-reference consistency and pairwise separation completeness |
| 6 | `validate_coverage` | INFO/WARNING | Quantitative hypotheses without analyses, empirical assumptions without falsifiable consequences, stressed predictions |
| 7 | `validate_assumption_testability` | WARNING | Assumptions with falsifiable consequence but no testing predictions |
| 8 | `validate_implicit_assumption_coverage` | INFO | Assumptions silently underpinning predictions with no test coverage |
| 9 | `validate_foundational_hypothesis_deps` | WARNING | Foundational hypotheses with `depends_on` entries |
| 10 | `validate_conditional_assumption_pressure` | WARNING | Confirmed/stressed predictions conditional on assumptions whose testers were refuted |
| 11 | `validate_stress_criteria` | WARNING | Stressed predictions without explicit stress criteria |
| 12 | `validate_retracted_observation_citations` | WARNING/INFO | Observations referencing retracted hypotheses or retracted observations linked to predictions |
| 13 | `validate_objective_abandonment_impact` | WARNING | Hypotheses whose only motivating objectives are terminal |
| 14 | `validate_load_bearing_assumption_coverage` | CRITICAL/WARNING | HIGH or LOAD_BEARING assumptions with no test coverage |
| 15 | `validate_supersession_chains` | CRITICAL/WARNING | Dangling or missing supersession references |
| 16 | `validate_testability_regime_consistency` | WARNING | NOT_YET_TESTABLE predictions with non-UNMEASURED regime |
| 17 | `validate_goal_objective_criteria` | WARNING | GOAL objectives without success criteria |
| 18 | `validate_compromised_observation_basis` | WARNING | Confirmed/stressed predictions with disputed or retracted observations |
| 19 | `validate_supersession_status_consistency` | WARNING | Predictions with inconsistent supersession link/status pairing |
| 20 | `validate_refutation_criteria` | WARNING | Refuted predictions without explicit refutation criteria |
| 21 | `validate_observed_but_pending` | INFO | Predictions with recorded evidence still in PENDING status |
| 22 | `validate_deferred_hypothesis_active_predictions` | WARNING | Deferred hypotheses with active predictions |
| 23 | `validate_orphaned_predictions` | INFO | Predictions with no hypothesis derivation chain |
| 24 | `validate_falsified_assumption_impact` | CRITICAL/WARNING | Active entities depending on FALSIFIED or QUESTIONED assumptions |
| 25 | `validate_adjudication_has_observations` | WARNING | Adjudicated predictions with no linked observations |
| 26 | `validate_adjudication_rationale` | WARNING | Adjudicated predictions without rationale |
| 27 | `validate_hypothesis_refutation_criteria` | INFO | Active hypotheses with predictions but no refutation criteria |
| 28 | `validate_discovery_integration_consistency` | WARNING | INTEGRATED discoveries with no structural links |
| 29 | `validate_supersession_cycles` | CRITICAL | Cycles in supersession chains |
| 30 | `validate_hypothesis_empirical_interface` | INFO | Active hypotheses with no predictions |
| 31 | `validate_disconnected_dead_ends` | INFO | Dead ends with no structural links |

---

## Error Hierarchy

All domain exceptions inherit from `EpistemicError`:

- **`DuplicateIdError`**: Entity ID already exists in the graph.
- **`BrokenReferenceError`**: Referenced entity does not exist, or hard references still exist during removal.
- **`CycleError`**: Mutation would create a dependency cycle in the hypothesis or assumption DAG.
- **`InvariantViolation`**: Field combination is logically impossible or transition is not allowed.

---

## Architecture

Episteme is built around a pure **epistemic kernel** with zero external
dependencies. It defines the entity model, the `EpistemicGraph` aggregate
root, and all invariant rules. Nothing in the kernel touches a file, a
database, or a network socket.

Dependencies form a directed acyclic graph with the kernel at the center --
not a strict linear onion:

```
+---------------------------------------------------------+
|  Interface Layer                                        |
|  cli, humans & scripts    mcp, AI agents                |
+-------------+------------------+------------------------+
              |                  |
+-------------v-----------+  +--v--------------------------+
|  Client                 |  |  View Services              |
|  EpistemeClient,        |  |  health . status .          |
|  persistence, typed     |  |  metrics . evidence         |
|  helpers                |  |  (read-only, kernel only)   |
+-------------+-----------+  +--+------ ------------------+
              |                  |
+-------------v-----------+     |
|  Control Plane          |     |
|  gateway . validate .   |     |
|  check . export .       |     |
|  prose . render         |     |
+-------------+-----------+     |
              |                 |
+-------------v-----------------v---------+
|  Epistemic Kernel -- pure Python, no I/O                |
|  types . model . graph . invariants . errors . ports    |
+---------------------------------------------------------+
```

The **client** calls the control plane for mutations and the kernel for types.
**Views** depend *only* on kernel protocols (`EpistemicGraphPort`,
`GraphValidator`) -- they have zero imports from the control plane or client.
**Adapters** (json_repository, transaction_log, renderer) implement kernel
protocols and are injected at runtime.

All mutations route through a single `Gateway`. A bug fixed at the gateway is
fixed for every interface simultaneously.

The kernel depends on **nothing** outside the standard library. Protocol-based
ports (`EpistemicGraphPort`, `GraphRepository`, `GraphValidator`) provide
dependency inversion so the control plane and adapters can be swapped without
touching the domain logic.

---

## Package Layout

```
src/episteme/
|-- __init__.py              # Package root, version, connect()
|-- config.py                # ProjectContext, ProjectPaths, runtime configuration
|-- epistemic/               # Epistemic kernel -- pure Python, zero I/O
|   |-- types.py             # 11 typed IDs, enums, Finding, transition tables,
|   |                        #   RefutationImpact, AssumptionSupportStatus, ParameterImpact
|   |-- model.py             # 11 entity dataclasses
|   |-- graph.py             # EpistemicGraph aggregate root, all mutations and queries
|   |-- invariants.py        # 31 pure validator functions + validate_all
|   |-- errors.py            # Domain exception hierarchy
|   |-- codec.py             # Serialization between entities and primitive payloads
|   |-- ports.py             # Protocol re-exports
|   |-- _ports_graph.py      # EpistemicGraphPort and GraphRepository protocols
|   |-- _ports_services.py   # GraphValidator, ProseSync, TransactionLog protocols
|   `-- _ports_artifacts.py  # Artifact, ArtifactSink, GraphExporter protocols
|-- controlplane/            # Core services
|   |-- gateway.py           # Single mutation/query boundary
|   |-- _gateway_catalog.py  # Resource and query spec tables
|   |-- _gateway_results.py  # GatewayResult types
|   |-- factory.py           # Wires concrete implementations into Gateway
|   |-- validate.py          # Domain-wide invariant orchestration
|   |-- check.py             # Staleness detection, reference integrity
|   |-- prose.py             # Managed-prose sync and verification
|   |-- render.py            # SHA-256 fingerprint cache + incremental render
|   `-- export.py            # Export orchestration
|-- client/                  # Python API surface
|   |-- __init__.py          # EpistemeClient, connect()
|   |-- _client.py           # Client implementation
|   |-- _core.py             # Generic gateway verbs, persistence, context manager
|   |-- _hypothesis.py       # Hypothesis-specific helpers
|   |-- _registry.py         # Entity registry
|   |-- _resources.py        # Typed entity helpers
|   |-- _structure.py        # Graph structure helpers
|   `-- _types.py            # ClientResult, EpistemeClientError
|-- views/                   # Read-only composed summaries
|   |-- evidence.py          # EvidenceSummary: per-hypothesis evidence picture
|   |-- health.py            # HealthReport (stub)
|   |-- status.py            # ProjectStatus (stub)
|   `-- metrics.py           # PredictionMetrics, GraphMetrics (stub)
`-- interfaces/              # Thin adapters, no business logic (planned)
```

---

## Design Principles

| Principle | Application |
|-----------|-------------|
| **Immutable aggregate root** | Every mutation returns a new `EpistemicGraph`. The old instance is never modified. Free undo/redo, no state corruption. |
| **Fail Fast** | Broken references, cycles, impossible field combinations, and illegal transitions are caught at mutation time, not discovered later. |
| **Single gateway** | All mutations flow through one boundary. No interface-specific business logic. |
| **Protocol-based ports** | `EpistemicGraphPort` is a Protocol, not an abstract base class. Any matching implementation (in-memory, DB-backed, test double) works without inheritance. |
| **Copy-on-write efficiency** | `_copy()` creates new dict instances but shares entity references. Only mutated entities are deep-copied: O(mutated) not O(total). |
| **Domain-neutral vocabulary** | Works for physics, chemistry, biology, engineering, ML, medicine, social science. The vocabulary is general empirical reasoning. |
| **Audit scaffold** | Surfaces structural facts. Never prescribes research direction or makes logical judgments. |
| **Consumer model** | Records results from researcher-run analyses. Never executes code itself. |
| **Zero kernel dependencies** | The epistemic kernel uses only the Python standard library. No supply-chain risk in the domain layer. |

---

## Quick Start

> **Not yet published to PyPI.** Install from source for development.

```bash
git clone https://github.com/cdowd010/episteme
cd episteme
pip install -e ".[dev]"
```

```python
from episteme.epistemic.graph import EpistemicGraph
from episteme.epistemic.model import (
    Hypothesis, Assumption, Prediction, Observation, Objective,
)
from episteme.epistemic.types import (
    HypothesisId, AssumptionId, PredictionId, ObservationId, ObjectiveId,
    HypothesisType, AssumptionType, ObjectiveKind,
    ConfidenceTier, EvidenceKind, MeasurementRegime,
)
from datetime import date

graph = EpistemicGraph()

# Register an objective
graph = graph.register_objective(
    Objective(
        id=ObjectiveId("OBJ-001"),
        title="Catalysis Framework",
        kind=ObjectiveKind.EXPLANATORY,
    )
)

# Register an assumption
graph = graph.register_assumption(
    Assumption(
        id=AssumptionId("A-001"),
        statement="Detector is calibrated",
        type=AssumptionType.EMPIRICAL,
        falsifiable_consequence="Calibration check fails",
    )
)

# Register a hypothesis
graph = graph.register_hypothesis(
    Hypothesis(
        id=HypothesisId("H-001"),
        statement="Catalyst X increases yield by 15%",
        type=HypothesisType.FOUNDATIONAL,
        refutation_criteria="Replicated null result",
        assumptions={AssumptionId("A-001")},
        objectives={ObjectiveId("OBJ-001")},
    )
)

# Register a prediction
graph = graph.register_prediction(
    Prediction(
        id=PredictionId("P-001"),
        observable="yield",
        predicted=0.15,
        hypothesis_ids={HypothesisId("H-001")},
        tier=ConfidenceTier.FULLY_SPECIFIED,
        evidence_kind=EvidenceKind.NOVEL_PREDICTION,
        measurement_regime=MeasurementRegime.MEASURED,
        refutation_criteria="Yield increase < 5%",
        stress_criteria="Yield increase 5-10%",
    )
)

# Register an observation
graph = graph.register_observation(
    Observation(
        id=ObservationId("OBS-001"),
        description="Controlled experiment result",
        value=0.148,
        uncertainty=0.012,
        date=date(2026, 4, 15),
        predictions={PredictionId("P-001")},
    )
)

# Validate the graph
from episteme.epistemic.invariants import validate_all
findings = validate_all(graph)
for f in findings:
    print(f"{f.severity.name}: [{f.source}] {f.message}")
```

### Running Tests

```bash
pip install -e ".[dev]"
pytest                    # 112 tests
pytest --cov              # with coverage
```

---

## Supported Workflows

Episteme is designed to support any STEM research or engineering workflow:

- **Hypothetico-deductive** (classical): Hypothesis -> Prediction -> Observation -> Adjudicate
- **Inductive / exploratory**: Observation -> Objective(EXPLORATORY) -> Hypothesis
- **Engineering / goal-directed**: Objective(GOAL) with success criteria -> Hypothesis -> Prediction -> iterate via `supersedes`
- **Iterative refinement**: Supersession chains on predictions, hypotheses, and objectives
- **Paradigm shifts**: Objective(EXPLANATORY) -> SUPERSEDED, validators flag orphaned motivations
- **Negative results**: DeadEnd entity captures what was tried and why it failed
- **Multi-investigator**: Independence groups and pairwise separations track evidence independence

---

## Development Status

| Milestone | Scope | Status |
|-----------|-------|--------|
| 1 | **Epistemic kernel**: entity model, aggregate root, invariant validators, typed queries | **Complete** (11 entities, 31 validators, 112 tests) |
| 2 | **Views**: EvidenceSummary per-hypothesis report | **Complete** |
| 3 | **Python API**: `connect()`, entity register/get/list/transition helpers | In progress |
| 4 | **Control plane**: gateway, staleness detection, export, render | In progress |
| 5 | **Interface backfill**: CLI and MCP as thin delegates over the gateway | Pending |
| 6 | **Documentation**: worked examples, terminology guide | Pending |

---

## License

Apache License 2.0. See [LICENSE](LICENSE).
