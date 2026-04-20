# Episteme

*Versioned, invariant-enforced tracking for the epistemic structure of research.*

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![License: Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Status: Early Development](https://img.shields.io/badge/status-early%20development-orange.svg)](TRACKER.md)

> **Early development.** The epistemic kernel is implemented and tested
> (11 entity types, 31 validators, 112 tests). The Python API, persistence,
> and interface layers are in progress.
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
about the graph — missing links, untested assumptions, stale analyses,
compromised observation bases, supersession inconsistencies — so you can act on
them.

Episteme is an **audit scaffold**, not a reasoning engine. It makes the
reasoning visible and keeps it honest. The researcher (or an AI agent)
decides what to do about what it finds.

---

## Vision

Episteme is a standalone tool. You use it directly — from Python, from a CLI,
from a notebook — to track the epistemic structure of your research. That is
the primary product, and it works without any AI involvement.

But the architecture is designed from day one for a second mode of operation:
**AI-assisted and AI-autonomous research**.

### Three modes of interaction

| Mode | Who drives | What the AI does |
|------|-----------|-----------------|
| **Manual** | Human researcher | Episteme is a library. You register entities, run validators, query the graph. No AI required. |
| **Assistant** | Human researcher, AI helps | The AI acts as an epistemic bookkeeper. When you say *"I think X causes Y,"* it registers a hypothesis, surfaces the validator findings, and uses them as a Socratic checklist: *"To make this testable, what prediction can we derive?"* |
| **Autonomous** | AI agent, human supervises | The AI is given an `Objective` and uses Episteme as its internal world model to plan, execute, and evaluate research cycles. The invariant logic gate prevents it from advancing its state without valid epistemic reasoning. |

The most interesting case is the **hybrid**: a human sets the objectives and
key assumptions, releases an autonomous agent to run N analysis cycles, then
returns to find a fully versioned, queryable epistemic graph showing exactly
how the agent reached its conclusions — with every reasoning step legible and
auditable.

### Why the architecture supports this

**Structural constraint as a form of AI safety.** Most AI safety work operates
at the output layer — RLHF, output filtering, guardrails on responses.
Episteme operates at the *reasoning* layer. The kernel enforces 31+
invariants on every write. An agent using Episteme as its world model cannot
silently hallucinate progress — it must register a hypothesis, derive a
prediction, obtain an observation, and feed it back through the Gateway.
The Gateway blocks circular reasoning, orphaned predictions, invalid
transitions, and self-contradictory evidence claims.

**Queryable long-term memory.** A large research graph — 200 hypotheses, 800
predictions, 2000 observations — does not fit in a context window. But the
agent does not need to load the whole graph. It queries the Gateway: *"What is
the blast radius of refuting Assumption A-01?"* and gets a precise,
invariant-enforced traversal — not a fuzzy similarity search. This is how
Episteme solves the context-window problem for long-running research.

**Multi-agent coordination.** The single-gateway mutation boundary, copy-on-write
semantics, and transaction log provide the coordination substrate for research
swarms: a primary researcher agent, a QC agent running validators against the
primary's graph (structural peer review), and domain-specialized agents
querying specific graph slices — all sharing one source of truth.

---

## Quick Start

```bash
git clone https://github.com/cdowd010/episteme
cd episteme
pip install -e ".[dev]"
```

```python
import episteme as ep

with ep.connect() as client:
    # Define what you're trying to explain
    client.register_objective(
        id="OBJ-001",
        title="Catalysis Framework",
        kind="explanatory",
        status="active",
    )

    # State what you're taking as given
    client.register_assumption(
        id="A-001",
        statement="Detector is calibrated",
        type="empirical",
        falsifiable_consequence="Calibration check fails",
    )

    # Make a claim
    client.register_hypothesis(
        id="H-001",
        statement="Catalyst X increases yield by 15%",
        type="foundational",
        refutation_criteria="Replicated null result",
        assumptions=["A-001"],
    )

    # Derive a testable consequence
    client.register_prediction(
        id="P-001",
        observable="yield",
        predicted=0.15,
        hypothesis_ids=["H-001"],
        tier="fully_specified",
        evidence_kind="novel_prediction",
        measurement_regime="measured",
        refutation_criteria="Yield increase < 5%",
    )

    # Record what you measured
    client.register_observation(
        id="OBS-001",
        description="Controlled experiment result",
        value=0.148,
        uncertainty=0.012,
        date="2026-04-15",
        predictions=["P-001"],
    )

    # Check for structural problems
    findings = client.validate()
    for f in findings:
        print(f"{f.severity.name}: [{f.source}] {f.message}")
```

> **Note:** `connect()` and the client helpers are in progress (Milestone 3).
> The epistemic kernel is complete and usable directly — see
> [EXAMPLES.md](EXAMPLES.md) for gateway-level usage.

### Running Tests

```bash
pytest                    # 112 tests
pytest --cov              # with coverage
```

---

## Core Capabilities

- **Register** hypotheses, assumptions, predictions, observations, analyses,
  parameters, objectives, discoveries, independence groups, pairwise
  separations, and dead ends in a typed, versioned graph
- **Enforce** referential integrity, DAG acyclicity, bidirectional backlinks,
  tier constraints, and field-level consistency at write time
- **Validate** the full epistemic graph on demand against 31 semantic
  invariant validators covering retracted citations, circular reasoning,
  tier consistency, evidence independence, coverage gaps, staleness,
  supersession integrity, and more
- **Track evidence** through prediction tiers (`FULLY_SPECIFIED`,
  `CONDITIONAL`, `FIT_CHECK`) with explicit independence-group accounting
  and three orthogonal classification axes (tier, evidence kind, measurement
  regime)
- **Detect staleness** when a parameter changes and propagate impact through
  analyses, hypotheses, and predictions
- **Trace blast radius** with typed queries: `refutation_impact`,
  `assumption_support_status`, `parameter_impact`
- **Lifecycle management** with guarded status transitions for seven entity
  types, each with an explicit transition table and terminal states
- **Supersession chains** across predictions, hypotheses, and objectives with
  automatic predecessor transition and cycle detection

Episteme never executes analyses. Researchers run their own tools (Python, R,
SageMath, Jupyter) and record outcomes. Episteme records provenance, enforces
structure, and tracks what changed.

---

## The Epistemic Graph

The `EpistemicGraph` is the aggregate root. All mutations return a new
immutable graph instance (copy-on-write). The old instance is never modified,
giving free undo/redo semantics.

### Entities (11 types)

| Entity | Role |
|--------|------|
| **Hypothesis** | Falsifiable assertion. Forms a DAG via `depends_on`. `FOUNDATIONAL` or `DERIVED`, `QUANTITATIVE` or `QUALITATIVE`. |
| **Assumption** | Premise taken as given. `EMPIRICAL` or `METHODOLOGICAL`. Criticality from `LOW` to `LOAD_BEARING`. |
| **Prediction** | Testable consequence of hypotheses. Three orthogonal axes: confidence tier, evidence kind, measurement regime. |
| **Observation** | Raw empirical data. Tracks statistical and systematic uncertainty separately. |
| **Analysis** | Provenance pointer to researcher-run code. Tracks result hash and date for staleness detection. |
| **Parameter** | Physical or mathematical constant. Changes propagate to dependent analyses. |
| **Objective** | Research motivation. `EXPLANATORY`, `GOAL`, or `EXPLORATORY`. Hub entity linking hypotheses, predictions, and discoveries. |
| **Discovery** | Significant finding. Soft links to hypotheses and predictions. |
| **Dead End** | Failed approach that constrains the hypothesis space. |
| **Independence Group** | Predictions sharing a common derivation chain. |
| **Pairwise Separation** | Documents why two independence groups provide genuinely separate evidence. |

Every entity type with a status field has an explicit transition table with
terminal states enforced at mutation time. The graph automatically maintains
bidirectional backlinks (e.g., registering a prediction that cites a hypothesis
updates both the prediction's `hypothesis_ids` and the hypothesis's
`predictions` backlink).

---

## Architecture

Episteme is built around a pure **epistemic kernel** with zero external
dependencies. Dependencies form a directed acyclic graph with the kernel at
the center:

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
+-------------+-----------+  +--+--------------------------+
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

All mutations route through a single **Gateway**. The kernel depends on
nothing outside the standard library. Views depend only on kernel protocols —
zero control-plane imports. Protocol-based ports (`EpistemicGraphPort`,
`GraphRepository`, `GraphValidator`) provide dependency inversion so any layer
can be swapped without touching the domain logic.

---

## Supported Workflows

Episteme supports any STEM research or engineering methodology:

- **Hypothetico-deductive** (classical): Hypothesis → Prediction → Observation → Adjudicate
- **Inductive / exploratory**: Observation → Objective(EXPLORATORY) → Hypothesis
- **Engineering / goal-directed**: Objective(GOAL) with success criteria → Hypothesis → Prediction → iterate via `supersedes`
- **Iterative refinement**: Supersession chains on predictions, hypotheses, and objectives
- **Paradigm shifts**: Objective(EXPLANATORY) → SUPERSEDED, validators flag orphaned motivations
- **Negative results**: DeadEnd entity captures what was tried and why it failed
- **Multi-investigator**: Independence groups and pairwise separations track evidence independence

---

## Development Status

| Milestone | Scope | Status |
|-----------|-------|--------|
| 1 | Epistemic kernel — entity model, aggregate root, invariant validators, typed queries | **Complete** |
| 2 | Views — EvidenceSummary per-hypothesis report | **Complete** |
| 3 | Python API — `connect()`, entity register/get/list/transition helpers | In progress |
| 4 | Control plane — gateway, staleness detection, export, render | In progress |
| 5 | Interface layer — CLI and MCP server as thin delegates over the gateway | Planned |
| 6 | Documentation — worked examples, terminology guide | Planned |

---

## License

Apache License 2.0. See [LICENSE](LICENSE).
