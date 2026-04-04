# Horizon Rebuild Plan — From the Ground Up

*Unified build plan combining the product roadmap with a clean architecture
rebuild. Written for execution, not theory.*

---

## Table of Contents

1. [Goal](#1-goal)
2. [Why Rebuild Instead of Refactor](#2-why-rebuild-instead-of-refactor)
3. [Architecture: Control Plane, Gateway, and Principles](#3-architecture-control-plane-gateway-and-principles) *(includes 3.8: The Audit Scaffold Principle)*
4. [The Epistemic Web: Core Data Structure](#4-the-epistemic-web-core-data-structure)
5. [Phase 1 — Domain Core](#5-phase-1--domain-core)
6. [Phase 2 — Persistence, Testing, and Packaging](#6-phase-2--persistence-testing-and-packaging)
7. [Phase 3 — Gateway and Control-Plane Services](#7-phase-3--gateway-and-control-plane-services)
8. [Phase 4 — MCP, CLI, Init, Health](#8-phase-4--mcp-cli-init-health)
9. [Phase 5 — Human-First UX](#9-phase-5--human-first-ux)
10. [Phase 6 — Results Ingestion](#10-phase-6--results-ingestion)
11. [Backlog](#11-backlog)
12. [Principle Compliance Matrix](#12-principle-compliance-matrix)
14. [Clean Break from the Current Codebase](#14-clean-break-from-the-current-codebase)
15. [Standing Decisions](#15-standing-decisions)
16. [Data Flow Diagram](#16-data-flow-diagram)
17. [End-to-End Traces](#17-end-to-end-traces)
18. [Testing Strategy and Fixture Model](#18-testing-strategy-and-fixture-model)
19. [Where to Put New Code](#19-where-to-put-new-code)
20. [CI/CD Rollout](#20-cicd-rollout)

---

## 1. Goal

Horizon is an **audit scaffold for empirical research** — a structured graph
that tracks the epistemic chain connecting a research outcome back to its
foundational assumptions. Every link in that chain is documented, sourced,
and traversable. A researcher or AI agent that has the chain in hand can
audit the logical correctness of each step with their own domain knowledge.
The system makes the audit *possible*; the auditor does the reasoning.

AI agents are the primary target user. Horizon ships an MCP server so that
agents (Claude, Cursor, Copilot, etc.) can register research artifacts,
query the epistemic web, traverse derivation chains, and surface structural
gaps — all through a stable, tool-shaped API with no subprocess wrangling.

A standalone CLI is the secondary interface: it exists for human researchers
who want direct access and for scripting, testing, and debugging the product
itself. Every capability exposed over MCP is also reachable from the CLI.

Both surfaces share one backend: the control-plane gateway. If the gateway
is correct, both interfaces are correct.

The rebuild starts from the epistemic web — the core data structure — and
layers outward. Each phase ships something testable.

Horizon is a **control plane over a research data plane**. The epistemic web
is the domain kernel, but the product is larger than the kernel: the gateway,
validators, renderers, and health/view services all belong to the control plane.

---

## 2. Why Rebuild Instead of Refactor

The existing codebase has proven the *domain model* — claims, predictions,
assumptions, analysiss, independence groups, bidirectional
invariants, transactional mutations. These ideas are sound and battle-tested.

What's broken is the *wiring*:

- `_sync_compatibility_state()` in `horizon.py` is ~120 lines of
  monkey-patching that rewrites globals across 10+ modules at runtime
- Circular dependencies resolved through runtime function rebinding
- Modules are not independently testable
- No module boundary prevents reaching into any other module's state

Refactoring this in-place (the old Phase 2 plan) would require:
1. Writing characterization tests against the current fragile wiring
2. Threading `ProjectContext` through every module while keeping the old
   wiring alive as a fallback
3. Deleting the old wiring once everything passes
4. Repeating for every module

A clean rebuild avoids all of that. The existing codebase proved which
**ideas** are correct — gateway as mutation boundary, transactional writes,
bidirectional invariants, sandbox execution. We take those ideas and build
them right from scratch.

### What We Preserve

| Keep | Why |
|------|-----|
| JSON file format | Backward compatibility, human-readable, simple |
| CLI command surface | User muscle memory, agent tooling compatibility |
| Control-plane/data-plane split | It is the right product boundary: product code manages research state without embedding research content in the codebase |
| Gateway as a single mutation/query boundary | Centralizes writes, rollback, provenance, dry-run behavior, and stable external semantics |
| Transactional mutations (validate-after-write, rollback on failure) | Best architectural idea in current system |
| Incremental rendering (SHA-256 fingerprints) | Performance |
| Consumer model for analyses | Correctness — Horizon records results, does not execute code |
| Domain vocabulary (claims, assumptions, predictions, independence groups) | Correct domain modeling |
| Bidirectional invariants | Correct epistemic reasoning |
| Source provenance on all ingested data | Every link in the chain is traceable |

### What We Eliminate

| Remove | Why |
|--------|-----|
| `_sync_compatibility_state()` | Global state mutation |
| Module-level globals for paths | Untestable, fragile |
| Untyped `GATEWAY_RESOURCE_SPECS` dict-of-dicts | Replace the spec table, not the gateway concept itself |
| After-the-fact bidirectional link validation | Replaced by enforcement at mutation time |
| Wrapper functions that call `_sync_compatibility_state()` first | No global state to sync |
| `_ORIGINAL_*` snapshot variables | No state to snapshot |

---

## 3. Architecture: Control Plane, Gateway, and Principles

The first draft of this rebuild plan got one thing materially wrong: it
modeled Horizon mostly as a domain library with a CLI on top. That is too
small. Horizon is a **control plane** whose domain kernel is the epistemic
web.

### 3.1 The Right Top-Level Picture

- The **data plane** is the project state and artifacts: canonical registries,
    generated views, analyses, and recorded results.
- The **control plane** is the product code that manages that data plane:
    context building, gateway, validators, renderers, and health/view services.
- The **epistemic web** is the in-memory domain kernel inside the control
    plane, not the whole product.

This distinction matters because it keeps the rebuild from collapsing into
"just a graph library." The product is valuable because it manages the
research project end-to-end.

The filesystem and package layout need to reflect that. The top code folder
should be `src/horizon_research/`. `epistemic/` belongs *inside* that package
as the kernel data structure layer for storing and validating epistemic webs;
it should not be the umbrella package that everything else lives under.

### 3.2 Control-Plane Subsystems We Should Keep

1. **ProjectContext** — one explicit runtime contract for paths, config,
     caches, logs, and feature flags.
2. **Gateway** — the single mutation and query boundary exposed to both the
     MCP server and the CLI.
3. **MCP server** — the primary external API for AI agents. Exposes all
     gateway operations and traversal tools as typed MCP tools with structured
     `status`-first envelopes. Not aspirational — ships in Phase 4.
4. **Read-only services** — validate, render, health, status, export, traversal
     queries, and other computed read models.
5. **Results ingestion** — the researcher runs analyses using their own tools
     and records results via `horizon record` or the `record_result` MCP tool.
     Horizon is a consumer, not an executor.
6. **Governance layer** — sessions, boundaries, and close gates as opt-in.
7. **Outer-shell workspace tooling** — multi-program or repo-management tools
     stay outside the product core.

Not every old implementation detail survives. But these subsystem boundaries
were good ideas and should be preserved.

### 3.3 The Layer Cake

```
┌──────────────────────────────────────────────────────┐
│  Interface Layer (interfaces/) — equal peers         │
│  cli/   Humans + scripts (Click commands)            │
│  mcp/   AI agents (FastMCP + agent scaffolding)      │
│  rest/  future · gui/ future · sdk/ future           │
└─────────────────────┬────────────────────────────────┘
                      │  (no business logic in any interface)
┌─────────────────────▼────────────────────────────────┐
│  View Services (views/) — always available           │
│  health · render · status · metrics                  │
│  Read-only composed summaries + derived files        │
└─────────────────────┬────────────────────────────────┘
                      │
┌─────────────────────▼────────────────────────────────┐
│  Core Services (core/) — always available            │
│  Mutations:  gateway · results                       │
│  Queries:    validate · check · export               │
│  Policy:     automation (render-trigger table)       │
└─────────────────────┬────────────────────────────────┘
                      │
┌─────────────────────▼────────────────────────────────┐
│  Config (config.py) — runtime contract               │
│  HorizonConfig · ProjectContext · ProjectPaths       │
│  load_config() · build_context()                     │
└─────────────────────┬────────────────────────────────┘
                      │
┌─────────────────────▼────────────────────────────────┐
│  Infrastructure Adapters (adapters/)                 │
│  json_repository · results_repository                │
│  transaction_log · markdown_renderer                 │
└─────────────────────┬────────────────────────────────┘
                      │
┌─────────────────────▼────────────────────────────────┐
│  Epistemic Kernel (epistemic/) — pure Python, no I/O │
│  model · web · invariants · types · ports            │
└──────────────────────────────────────────────────────┘
                      │
┌─────────────────────▼────────────────────────────────┐
│  Data Plane — filesystem                             │
│  project/data/ (entity JSON) · project/views/ (md)  │
└──────────────────────────────────────────────────────┘
```

**Dependency rules (strictly enforced):**
- `epistemic` → stdlib only. Zero external imports.
- `adapters` → `epistemic` only.
- `config` → stdlib only.
- `core` → `epistemic`, `adapters`, `config`.
- `views` → `core`, `epistemic`, `config`.
- `interfaces/cli`, `interfaces/mcp` → all layers above. No business logic lives here.

**Principles:**
- **Equal interfaces**: `interfaces/cli` and `interfaces/mcp` are peers. Neither
    is primary. Both expose the same core/views services.
    No MCP-specific or CLI-specific business logic.
- **View/mutation separation**: view services never mutate the epistemic web
    (render is the one exception: it writes derived files, not canonical data).
- **Single config module**: `config.py` is the only place that reads
    `horizon.toml`. All services receive a `ProjectContext` — never the raw file.

### 3.4 Package Layout

All code paths below are relative to `src/horizon_research/` unless noted
otherwise. The Python import root is `horizon_research`.

```
src/
└── horizon_research/               # Top-level product package
    ├── __init__.py
    ├── __main__.py                 # `python -m horizon_research`
    ├── config.py                   # HorizonConfig, ProjectContext, ProjectPaths,
    │                               #   load_config(), build_context()
    ├── epistemic/                  # Layer 1: Kernel — pure Python, zero I/O
    │   ├── __init__.py
    │   ├── types.py                # Typed IDs, enums, Finding, Severity
    │   ├── model.py                # Entity dataclasses (Claim, Prediction, ...)
    │   ├── web.py                  # EpistemicWeb aggregate root
    │   ├── invariants.py           # Cross-entity validation rules
    │   └── ports.py                # WebRepository, WebRenderer, TransactionLog protocols
    ├── adapters/                   # Layer 2: Infrastructure — I/O implementations
    │   ├── __init__.py
    │   ├── json_repository.py      # Implements WebRepository
    │   ├── results_repository.py   # Implements ResultRecorder (Phase 6)
    │   ├── markdown_renderer.py    # Implements WebRenderer
    │   └── transaction_log.py      # JSONL provenance log
    ├── core/                       # Layer 3A: Core Services — mutations + queries
    │   ├── __init__.py
    │   ├── gateway.py              # Single mutation/query boundary
    │   ├── validate.py             # Structural validation (read-only)
    │   ├── check.py                # check_stale, check_refs, sync_prose
    │   ├── results.py              # record_result (Phase 6)
    │   ├── export.py               # Bulk JSON/markdown export
    │   └── automation.py           # Render-trigger policy table
    ├── views/                      # Layer 4: View Services — composed summaries
    │   ├── __init__.py
    │   ├── health.py               # Composed health report (validate + check)
    │   ├── render.py               # Incremental markdown generation (SHA-256 cache)
    │   ├── status.py               # Summary read model
    │   └── metrics.py              # Evidence statistics (tier A summary)
    └── interfaces/                 # Layer 5: Interface Adapters — equal peers, no business logic
        ├── __init__.py             # Documents the interface layer contract
        ├── cli/                    # Humans + scripts (Click commands)
        │   ├── __init__.py
        │   ├── main.py             # Click commands; thin wrappers over core/views
        │   └── formatters.py       # Rich tables, JSON fallback
        └── mcp/                    # AI agents (FastMCP)
            ├── __init__.py
            ├── server.py           # FastMCP entry point, tool registration
            └── tools.py            # Tool handlers; thin wrappers over core/views
            # future: rest/, gui/, sdk/ go here as equal peers
```

**Principles:**
- **Equal interfaces**: `interfaces/cli` and `interfaces/mcp` are peers. No business logic in either.
- **Acyclic dependencies**: `epistemic ← adapters ← core ← views ← interfaces/*`
- **Stable dependencies**: `epistemic/` changes least; `interfaces/*` change most.
- **No duplicated logic**: every MCP tool handler and CLI command calls the same
    core/views function. If a handler does more than parse + call + format,
    move the logic up.

### 3.5 The Gateway We Keep

The gateway absolutely belongs in the rebuild. The domain model does **not**
replace it. They solve different problems:

- The **domain** enforces epistemic invariants inside one in-memory web.
- The **gateway** owns the external mutation and query surface.

The gateway should be responsible for:

- resource-oriented register/get/list/set/transition/query operations
- payload parsing and normalization
- resource alias resolution (plural/hyphenated forms → canonical keys)
- dry-run semantics
- transaction orchestration
- provenance logging
- stable result envelopes for CLI and automation

Resource aliases allow flexible naming on the command line:

```python
GATEWAY_RESOURCE_ALIASES = {
    "claim": "claim", "claims": "claim",
    "prediction": "prediction", "predictions": "prediction",
    "failure": "failure", "failures": "failure",
    "summary": "session_summary", "session-summary": "session_summary",
    # ... maps plural/hyphenated forms to canonical keys
}
```

This is a data-driven design. Adding a new resource type should mean adding
one entry, not writing a new handler class.

The gateway should **not** be responsible for:

- storing canonical domain rules in untyped dict-of-dicts
- mutating module globals
- owning validation rules themselves
- formatting human CLI output

In other words: keep the gateway boundary, replace the old implementation.

```python
@dataclass
class GatewayResult:
        status: str          # "ok" | "error" | "CLEAN" | "BLOCKED" | "dry_run"
        changed: bool
        message: str
        findings: list[Finding]
        transaction_id: str | None = None
        data: dict | None = None  # resource data for get/list/query results


class Gateway:
        """Single mutation/query boundary for the control plane."""

        def __init__(
                self,
                context: ProjectContext,
                repo: WebRepository,
                validator: WebValidator,
                renderer: WebRenderer,
                prose_sync: ProseSync,
                tx_log: TransactionLog,
        ) -> None:
                self._context = context
                self._repo = repo
                self._validator = validator
                self._renderer = renderer
                self._prose_sync = prose_sync
                self._tx_log = tx_log
```

### 3.6 The Runtime Contract: ProjectContext

The original architecture was right to want one runtime contract object. The
new plan should preserve that idea explicitly.

```python
@dataclass
class HorizonConfig:
        project_dir: Path = Path("project")


@dataclass
class ProjectPaths:
        workspace: Path
        project_dir: Path
        data_dir: Path          # entity JSON files (claims.json, predictions.json, ...)
        views_dir: Path         # rendered markdown outputs
        cache_dir: Path
        render_cache_file: Path
        transaction_log_file: Path


@dataclass
class ProjectContext:
        workspace: Path
        config: HorizonConfig
        paths: ProjectPaths
```

Important rule: `ProjectContext` carries **data**, not callbacks. No monkey
patching. No hidden collaborators. It exists so every control-plane service can
be explicit about what project it is operating on.

### 3.7 Design Decisions

**Source pointer convention.** Every research content entity carries
`source: str | None`. The value is free-form but should follow a soft
prefix convention so renderers can detect the type and validators can
flag malformed references:

| Prefix | Example |
|--------|---------|
| `doi:` | `doi:10.1103/PhysRevLett.128.011801` |
| `arxiv:` | `arxiv:2201.12840` |
| `url:` | `url:https://physics.nist.gov/cgi-bin/cuu/Value?alph` |
| (plain) | `Weinberg, QFT Vol.1, p.123` or `NIST CODATA 2018` |
| `derived:` | `derived:C-001,C-002` |

`horizon show` renders `doi:` and `arxiv:` sources as clickable links.
`health_check` can flag sources that look malformed. No strict enforcement
at the type level — `str | None` is sufficient.

**Native Python types everywhere.** The domain model uses `dict`, `set`, and
`list` — not `Mapping`, `frozenset`, or `tuple`. The `EpistemicWeb` and the
gateway are the encapsulation boundaries, not the container types.

**Dataclasses, not frozen.** Entities are `@dataclass` with mutable fields.
Consistency is enforced by the aggregate root and the gateway transaction
boundary, not by pretending Python collections are immutable.

**Targeted dependencies for great UX.** The goal is a tool that feels as
natural to use as `requests`, `pandas`, or `numpy` — clean API, beautiful
output, sensible defaults, zero friction. To get there, we allow carefully
chosen dependencies at the CLI and adapter boundaries while keeping the
domain core pure Python.

Dependency philosophy:
- **Domain core (`epistemic/`)**: stdlib only. Zero external imports. This
  is the gravity well — it must be fast, portable, and free of supply-chain
  risk.
- **Core services (`core/`) and view services (`views/`)**: stdlib only.
  Business logic should not depend on third-party libraries.
- **CLI (`interfaces/cli/`)**: `click` for argument parsing and command
  composition. `rich` for terminal output (tables, panels, color, progress).
  These libraries are stable, well-maintained, and directly improve the
  user's experience.
- **MCP (`interfaces/mcp/`)**: `fastmcp` as an optional extra. The MCP
  server is not needed for CLI-only use.
- **Adapters (`adapters/`)**: stdlib (`json`, `pathlib`). Adapters stay
  thin and dependency-free.
- **Compute**: `numpy`, `scipy` as optional extras for analysiss
  that need them. Never required for core operations.

The dependency tree stays **shallow** — only direct dependencies we've
consciously chosen, no transitive dependency sprawl. If removing a
dependency would make the product worse to use, it earns its place. If
it only saves the developer a few lines of code internally, it doesn't.

### 3.8 The Audit Scaffold Principle

The most important constraint on Horizon's design is what it does **not** do.

**What Horizon does:**
- Records that Claim C-001 depends on Assumption A-003
- Maintains that A-003's `tested_by` set is populated when a prediction is registered against it
- Returns the full derivation chain for Prediction P-007 when queried
- Surfaces that Parameter P-001 changed after Analysis A-002 last recorded a result
- Reports that Assumption A-003 has a `falsifiable_consequence` but no predictions testing it

**What Horizon does not do:**
- Verify that the dependency from C-001 to A-003 is logically sound
- Assess whether a derivation is correct
- Judge whether a falsifiable consequence is actually falsifiable
- Determine whether a parameter value is appropriate for an analysis

This is not a limitation — it is a deliberate design choice. Software that maintains
referential integrity and tracks structured state is doing something it is genuinely good at.
Software that assesses logical correctness of a research argument is not — and worse,
doing it badly gives a researcher false confidence.

**The system is the audit scaffold. The human or AI agent is the auditor.**

Horizon's job is to make auditing *possible*: ensuring every link in the chain has a
documented source, every assumption is explicitly stated, and every step is traceable.
A researcher or AI agent that has the full structured chain in hand can assess the logical
correctness of each link with their own domain knowledge and reasoning.

#### The system surfaces structural facts. It never recommends.

Every output Horizon produces is a structural observation about the state of the graph —
not a prescription about what to do. The distinction in language matters:

| ❌ Prescriptive (avoid) | ✓ Structural (correct) |
|---|---|
| "You should add a prediction for Claim C-001" | "Claim C-001 has no linked predictions" |
| "This derivation may be incomplete" | "Prediction P-007 has no `derivation` prose" |
| "Consider testing Assumption A-003" | "Assumption A-003 has `falsifiable_consequence` but empty `tested_by`" |
| "Analysis A-002 may be stale" | "Parameter P-001 changed after Analysis A-002's last recorded result" |

The consumer — researcher or agent — decides what to do with those observations.
Horizon does not.

#### The traversal API is the primary value proposition.

Rather than doing the reasoning, Horizon exposes navigation primitives that enable reasoning:

- `get_prediction_chain(prediction_id)` — structured chain: Theory → Claims → Assumptions → Analysis → Results
- `get_assumption_coverage(claim_id)` — assumptions in the lineage with empty `tested_by`
- `get_structural_gaps()` — entities with missing documentation (no `source`, no `derivation`, no linked analysis)
- `get_stale_analyses()` — analyses whose `uses_parameters` values changed since last result was recorded

An AI agent calling these gets structured data it can reason over independently, with
domain knowledge Horizon does not have. A human researcher sees the same data in readable form.
The reasoning happens *outside* the system; the structure that makes reasoning *possible*
lives inside it.

#### The test for any new feature.

When a new feature is proposed, the audit scaffold principle provides the filter:

- Does this feature expose a **structural fact** about the web? Build it.
- Does this feature make a **logical judgment** about the web's content? Stop at surfacing
  the structural pattern and let the consumer reason.

The inference gap scanner (Phase 5) passes this test when framed as a structural navigator:
it reports graph states — claims with no linked predictions, assumptions with falsifiable
consequences but no tests, predictions with no derivation prose. It does not suggest what
new predictions to add or assess whether a derivation is logically sound.

---

## 4. The Epistemic Web: Core Data Structure

### 4.1 What Are We Modeling?

Research is a **directed graph with typed nodes and typed edges**:

- **Nodes** are epistemic artifacts: claims, assumptions, predictions,
  theories, discoveries, analyses, independence groups, parameters, concepts,
  dead ends
- **Edges** are typed relationships with **bidirectional invariants**: if
  claim C-024 depends on assumption A-007, then A-007 must list C-024 in
  `used_in_claims`

This graph is the audit scaffold. Every node is a documented step in the
chain from foundational assumptions to observed outcomes. Every edge is a
traceable link that a reviewer can follow.

This is not a chain (linear). It's not a tree (single parent). It's a
**web** — a directed graph with multiple node types, multiple edge types, and
cross-cutting constraints.

### 4.2 The Core Nouns

| Noun | Role | Key Relationships |
|------|------|-------------------|
| **Claim** | Atomic falsifiable assertion | depends_on → Claims, assumptions → Assumptions, analyses → Analyses |
| **Assumption** | Premise taken as given | used_in_claims → Claims (bidirectional with claim.assumptions); tested_by → Predictions (bidirectional with prediction.tests_assumptions) |
| **Prediction** | Testable consequence of claims | claim_ids → Claims, tests_assumptions → Assumptions (bidirectional with Assumption.tested_by), analysis → Analysis, independence_group → IndependenceGroup |
| **Analysis** | Researcher-run analytical work; Horizon records its results | claims_covered → Claims (bidirectional with claim.analyses); uses_parameters → Parameters (bidirectional with parameter.used_in_analyses) |
| **Independence Group** | Predictions sharing derivation | member_predictions → Predictions (bidirectional with prediction.independence_group) |
| **Theory** | Higher-level explanatory framework | related_claims → Claims, related_predictions → Predictions |
| **Discovery** | Significant research finding | references (free-form) |
| **DeadEnd** | Known dead end or abandoned direction; valuable negative result | related_predictions, related_claims (advisory) |
| **Parameter** | Physical/mathematical constant referenced by analyses | used_in_analyses → Analyses (bidirectional with analysis.uses_parameters) |
| **Concept** | Defined vocabulary term | standalone |
| **Research Goal** | Why the research is being done; what counts as success | type (primary/secondary/opportunistic), success_criteria, linked_predictions → Predictions |

### 4.3 The Invariants

These are the hard rules that define a consistent epistemic web:

1. **Bidirectional link integrity**: If A references B, B must back-reference A
   (claim↔assumption, claim↔analysis, prediction↔independence_group,
   prediction↔assumption via tests_assumptions↔tested_by,
   analysis↔parameter via uses_parameters↔used_in_analyses)
2. **Referential integrity**: Every referenced ID must exist
3. **Acyclicity**: Claim `depends_on` graph must be a DAG — no circular reasoning
4. **Tier constraints**: Tier A predictions must have 0 free parameters;
   Tier B must state `conditional_on`; measured predictions must have observed
   values
5. **Independence semantics**: Predictions in the same group share derivation;
   every pair of groups must document their separation basis
6. **Coverage**: Numerical claims should have analysiss;
   empirical [E]-type assumptions need falsifiable consequences

### 4.4 Domain-General by Design

Horizon's vocabulary is chosen to be **domain-neutral without sacrificing
power for quantitative domains**. The entity names, relationship types, and
invariants are properties of sound empirical reasoning, not of any specific
field.

The naming principle: use the most general term that preserves the concept's
meaning. If a term sounds "physics-y" but is actually standard across
empirical disciplines, keep it. If it genuinely narrows the concept, rename
it.

| Horizon Term | Why It's General |
|-------------|-----------------|
| **Claim** | Any falsifiable assertion. Physics: "E8 predicts W mass." Medicine: "Drug X reduces mortality." ML: "Attention suffices for sequences." |
| **Assumption** | A premise taken as given. Exists in every empirical field. |
| **Prediction** | A testable consequence. Not physics-specific — every empirical discipline makes predictions. |
| **Research Goal** | *Why* the research is being done and what counts as success. Separate from the epistemic web (which models *what* is known). Goals have typed success criteria and statuses so the system can recognize partial success — "we didn't prove X but G-003 was achieved en route." |
| **Independence Group** | Evidence clusters that share derivation. Applies to medicine (correlated endpoints), ML (correlated benchmarks), social science (non-independent samples). |
| **Confidence Tier (A/B/C)** | How strongly constrained the prediction is. A = zero free parameters. B = conditional. C = fit/consistency. This hierarchy applies to any quantitative discipline. |
| **Measurement Regime** | Whether evidence exists: measured, bound_only, unmeasured. Medicine uses "observed/censored." ML uses "evaluated/not_evaluated." The abstraction is the same: is evidence available? |
| **Specification** | The relationship being tested. Physics: a formula. Medicine: a statistical model. ML: a performance metric. |
| **Verification Script** | A program that checks a prediction. Language-agnostic, domain-agnostic. |

**What we don't do**: invent new jargon. "Claim" is clearer than "epistemic
assertion." "Prediction" is clearer than "testable consequence node." Keep
the vocabulary close to how researchers actually talk.

**Power for quantitative domains**: The tier system, tolerance-based
verification, numeric predictions with observed/predicted values, free
parameter counting, and sensitivity analysis all serve quantitative work
(physics, ML, computational biology, economics) without being physics-specific.
Qualitative domains (history, philosophy, some social science) can use the
same entities with `category: "qualitative"` and descriptive rather than
numeric predictions.

### 4.5 Vocabulary Mapping Guide

Different fields use different vocabulary for the same concepts. Horizon
uses general terms; researchers should map their domain language:

| Horizon | Physics | Medicine | Machine Learning | Social Science |
|---------|---------|----------|-----------------|----------------|
| Claim | Theoretical prediction | Theory | Architecture claim | Theory |
| Assumption | Physical/mathematical premise | Study assumption | Training assumption | Methodological assumption |
| Prediction | Observable quantity | Primary endpoint | Benchmark score | Measured outcome |
| Tier A | Zero free params | Pre-registered primary | Zero-shot eval | Pre-registered |
| Tier B | Conditional prediction | Secondary endpoint | Few-shot eval | Exploratory |
| Measurement Regime: measured | Published data | Trial completed | Benchmark scored | Survey collected |
| Measurement Regime: bound_only | Upper/lower bound | Interim analysis | Partial eval | Pilot data |
| Independence Group | Sector (electroweak, QCD) | Organ system | Task family | Study population |
| Specification | Mathematical formula | Statistical model spec | Metric definition | Operationalization |

### 4.6 What the Web Looks Like Across Domains

**Physics:**
```
Claim: "E8 predicts the W boson mass"
  └─ Assumption: "Gauge group is compact and simple"
  └─ Prediction: "W mass = 80.379 GeV" (Tier A, measured, observed=80.377)
       └─ Script: gauge_couplings.py
       └─ IndependenceGroup: "electroweak_sector"
```

**Machine Learning:**
```
Claim: "Attention is sufficient for sequence modeling"
  └─ Assumption: "Training data is i.i.d."
  └─ Prediction: "BLEU > 28.0 on WMT14 EN-DE" (Tier A, measured, observed=28.4)
       └─ Script: train_and_evaluate.py
       └─ IndependenceGroup: "translation_benchmarks"
```

**Medicine:**
```
Claim: "Drug X reduces mortality in population Y"
  └─ Assumption: "No unmeasured confounders"
  └─ Prediction: "Hazard ratio < 0.8" (Tier RCT, measured, observed=0.72)
       └─ Script: survival_analysis.R
       └─ IndependenceGroup: "cardiovascular_endpoints"
```

Same structure. Same invariants. Different vocabulary.

---

## 5. Phase 1 — Domain Core

**Goal:** Build and fully test the epistemic web with zero I/O, zero
dependencies. This is the gravity well — get it right, and everything else
falls into place.

### 5.1 Type Foundation (`epistemic/types.py`)

```python
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
AssumptionId = NewType("AssumptionId", str)
PredictionId = NewType("PredictionId", str)
TheoryId = NewType("TheoryId", str)
DiscoveryId = NewType("DiscoveryId", str)
AnalysisId = NewType("AnalysisId", str)
IndependenceGroupId = NewType("IndependenceGroupId", str)
ParameterId = NewType("ParameterId", str)
ConceptId = NewType("ConceptId", str)
DeadEndId = NewType("DeadEndId", str)


# ── Severity ──────────────────────────────────────────────────────

class Severity(Enum):
    INFO = auto()
    WARNING = auto()
    CRITICAL = auto()


@dataclass
class Finding:
    """One validation result."""
    severity: Severity
    source: str
    message: str


# ── Confidence tiers ──────────────────────────────────────────────

class ConfidenceTier(Enum):
    """How strongly a prediction is constrained.
    A: Zero free parameters — pure prediction from theory.
    B: Conditional on stated assumptions beyond the core theory.
    C: Fit/consistency check — not a novel prediction.
    """
    A = "A"
    B = "B"
    C = "C"


# ── Evidence classification ───────────────────────────────────────

class EvidenceKind(Enum):
    NOVEL_PREDICTION = "novel_prediction"
    RETRODICTION = "retrodiction"
    FIT_CONSISTENCY = "fit_consistency"


class MeasurementRegime(Enum):
    MEASURED = "measured"
    BOUND_ONLY = "bound_only"
    UNMEASURED = "unmeasured"


class PredictionStatus(Enum):
    CONFIRMED = "CONFIRMED"
    STRESSED = "STRESSED"
    REFUTED = "REFUTED"
    PENDING = "PENDING"
    NOT_YET_TESTABLE = "NOT_YET_TESTABLE"


class DeadEndStatus(Enum):
    ACTIVE = "active"
    RESOLVED = "resolved"
    ARCHIVED = "archived"
```

**Principles:** Encapsulation (typed IDs prevent mixing), KISS (plain enums
and dataclasses), Open/Closed (tiers can become registry-based later without
changing the interface).

### 5.2 Entity Classes (`epistemic/model.py`)

All entities use native Python types: `set`, `list`, `dict`. No `frozenset`,
no `tuple`, no `Mapping`. Relationships are expressed through typed ID
references, not object references.

```python
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
    AssumptionId, ClaimId, ConfidenceTier, DiscoveryId, EvidenceKind,
    DeadEndId, DeadEndStatus, TheoryId, IndependenceGroupId,
    MeasurementRegime, ParameterId, PredictionId, PredictionStatus, AnalysisId,
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
    tested_by: set[PredictionId] = field(default_factory=set)  # bidirectional with Prediction.tests_assumptions
    source: str | None = None                    # doi:..., arxiv:..., url, citation, or "derived from ..."
    notes: str | None = None


@dataclass
class Prediction:
    """A testable consequence of one or more claims.

    'claim_ids' is the set of claims that jointly imply this prediction —
    the logical derivation chain. Most non-trivial predictions require
    multiple claims together.

    'tests_assumptions' is the set of assumptions this prediction was
    explicitly designed to test. Bidirectional with Assumption.tested_by.

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

    Horizon does not run analyses. 'path' and 'command' are provenance
    pointers — the researcher runs the analysis in their own environment
    and records the result via `horizon record`. The git SHA captured at
    record time, combined with path, gives a complete immutable provenance
    chain: path + SHA + recorded value.

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
    Enables staleness detection in health_check.
    """
    id: ParameterId
    name: str
    value: Any                          # numeric, string, or structured
    unit: str | None = None             # SI or domain unit, human-readable
    uncertainty: Any = None             # absolute uncertainty, same type as value
    source: str | None = None           # citation or derivation note
    used_in_analyses: set[AnalysisId] = field(default_factory=set)
    notes: str | None = None
```

**Principles:**
- **Single Responsibility**: Each entity describes one epistemic concept.
  No entity knows how to serialize itself or render to markdown.
- **Law of Demeter**: Entities hold IDs, not object references. To traverse,
  go through the web.
- **Composition over Inheritance**: No entity inherits from another. Shared
  structural patterns (has status, has notes) are coincidence, not hierarchy.
- **KISS**: Plain dataclasses, native Python types.
- **Encapsulation**: External code should use the web's methods to mutate
  entities, not modify entity fields directly.

### 5.3 The Aggregate Root (`epistemic/web.py`)

The `EpistemicWeb` is the **single entry point for all domain operations**.
It enforces every invariant. External code never modifies entities directly —
it calls methods on the web, and the web ensures consistency.

```python
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
    Analysis, Assumption, Claim, Concept, DeadEnd, Discovery,
    IndependenceGroup, PairwiseSeparation, Parameter, Prediction, Theory,
)
from .types import (
    AnalysisId, AssumptionId, ClaimId, ConceptId, DeadEndId, DiscoveryId,
    Finding, IndependenceGroupId, ParameterId, PredictionId, Severity, TheoryId,
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
    pairwise_separations: list[PairwiseSeparation] = field(default_factory=list)
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
        """All assumptions reachable through a claim and its ancestors."""
        all_claims = self.claim_lineage(cid) | {cid}
        result: set[AssumptionId] = set()
        for ancestor_id in all_claims:
            claim = self.claims.get(ancestor_id)
            if claim:
                result.update(claim.assumptions)
        return result

    # ── Mutations (return new web) ────────────────────────────────

    def register_claim(self, claim: Claim) -> EpistemicWeb:
        """Add a claim. Enforces: no duplicates, refs exist, no cycles,
        bidirectional links updated."""
        if claim.id in self.claims:
            raise DuplicateIdError(f"Claim {claim.id} already exists")
        self._check_refs_exist(claim.assumptions, self.assumptions, "assumption")
        self._check_refs_exist(claim.depends_on, self.claims, "claim")
        self._check_refs_exist(claim.analyses, self.scripts, "script")
        self._check_no_cycle_with(claim)

        new = self._copy()
        # Deep-copy the incoming entity so a caller who keeps a reference
        # cannot mutate the web's stored copy after registration. All
        # register_* methods follow this same pattern.
        new.claims[claim.id] = copy.deepcopy(claim)

        # Maintain bidirectional: assumption.used_in_claims
        for aid in claim.assumptions:
            new.assumptions[aid].used_in_claims.add(claim.id)

        # Maintain bidirectional: script.claims_covered
        for sid in claim.analyses:
            new.scripts[sid].claims_covered.add(claim.id)

        return new

    def register_assumption(self, assumption: Assumption) -> EpistemicWeb:
        """Add an assumption."""
        if assumption.id in self.assumptions:
            raise DuplicateIdError(f"Assumption {assumption.id} already exists")
        new = self._copy()
        new.assumptions[assumption.id] = assumption
        return new

    def register_prediction(self, prediction: Prediction) -> EpistemicWeb:
        """Add a prediction. Enforces: refs exist, bidirectional links updated."""
        if prediction.id in self.predictions:
            raise DuplicateIdError(f"Prediction {prediction.id} already exists")
        self._check_refs_exist(prediction.claim_ids, self.claims, "claim")
        self._check_refs_exist(prediction.tests_assumptions, self.assumptions, "assumption")
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
        """Add an analysis."""
        if analysis.id in self.analyses:
            raise DuplicateIdError(f"Analysis {analysis.id} already exists")
        new = self._copy()
        new.analyses[analysis.id] = analysis
        return new

    def register_theory(self, theory: Theory) -> EpistemicWeb:
        if theory.id in self.theories:
            raise DuplicateIdError(f"Theory {theory.id} already exists")
        new = self._copy()
        new.theories[theory.id] = theory
        return new

    def register_independence_group(self, group: IndependenceGroup) -> EpistemicWeb:
        if group.id in self.independence_groups:
            raise DuplicateIdError(f"Independence group {group.id} already exists")
        new = self._copy()
        new.independence_groups[group.id] = group
        return new

    def register_discovery(self, discovery: Discovery) -> EpistemicWeb:
        if discovery.id in self.discoveries:
            raise DuplicateIdError(f"Discovery {discovery.id} already exists")
        new = self._copy()
        new.discoveries[discovery.id] = discovery
        return new

    def register_dead_end(self, dead_end: DeadEnd) -> EpistemicWeb:
        if dead_end.id in self.dead_ends:
            raise DuplicateIdError(f"DeadEnd {dead_end.id} already exists")
        new = self._copy()
        new.dead_ends[dead_end.id] = dead_end
        return new

    def register_concept(self, concept: Concept) -> EpistemicWeb:
        if concept.id in self.concepts:
            raise DuplicateIdError(f"Concept {concept.id} already exists")
        new = self._copy()
        new.concepts[concept.id] = concept
        return new

    def add_pairwise_separation(self, sep: PairwiseSeparation) -> EpistemicWeb:
        """Document why two independence groups are separate."""
        if sep.group_a not in self.independence_groups:
            raise BrokenReferenceError(f"Group {sep.group_a} does not exist")
        if sep.group_b not in self.independence_groups:
            raise BrokenReferenceError(f"Group {sep.group_b} does not exist")
        new = self._copy()
        new.pairwise_separations.append(sep)
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
        self, fid: DeadEndId, new_status: DeadEndStatus,
    ) -> EpistemicWeb:
        """Change a dead end's status."""
        if fid not in self.dead_ends:
            raise BrokenReferenceError(f"DeadEnd {fid} does not exist")
        new = self._copy()
        new.dead_ends[fid].status = new_status
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
```

**Principles:**
- **Encapsulation**: The web is the only way to mutate the graph. Invariants
  are enforced at every mutation.
- **Abstraction**: `web.register_claim(claim)` hides all back-reference
  bookkeeping.
- **DRY**: Bidirectional link maintenance happens in exactly one place per
  relationship. The current Horizon system maintains these in gateway
  registration AND validates them after the fact. Here, they're maintained
  at the point of mutation.
- **Single Responsibility**: The web enforces graph consistency. It does not
  serialize, render, or execute anything.
- **KISS**: `_copy()` + mutate is the simplest possible immutable update
  pattern. No event system, no observer pattern.
- **Fail Fast**: Throws immediately on broken references or cycles.

### 5.4 Cross-Entity Validation (`epistemic/invariants.py`)

```python
"""Validation rules that span multiple entities.

These require looking at the web as a whole. Each function is pure:
(EpistemicWeb) -> list[Finding].

Structural invariants (refs exist, no cycles, bidirectional links) live
in web.py and are enforced at mutation time.

Semantic/coverage invariants live here and are checked on demand.
"""
from __future__ import annotations

from .types import Finding, Severity
from .web import EpistemicWeb


def validate_tier_constraints(web: EpistemicWeb) -> list[Finding]:
    """Tier A: 0 free params. Tier B: must state conditional_on."""
    findings: list[Finding] = []
    for pid, pred in web.predictions.items():
        if pred.tier.value == "A" and pred.free_params != 0:
            findings.append(Finding(
                Severity.CRITICAL,
                f"predictions/{pid}",
                f"Tier A prediction has {pred.free_params} free params (must be 0)",
            ))
        if pred.tier.value == "B" and not pred.conditional_on:
            findings.append(Finding(
                Severity.WARNING,
                f"predictions/{pid}",
                "Tier B prediction missing 'conditional_on'",
            ))
        if pred.measurement_regime.value == "measured" and pred.observed is None:
            findings.append(Finding(
                Severity.CRITICAL,
                f"predictions/{pid}",
                "measurement_regime='measured' requires an observed value",
            ))
        if pred.measurement_regime.value == "bound_only" and pred.observed_bound is None:
            findings.append(Finding(
                Severity.CRITICAL,
                f"predictions/{pid}",
                "measurement_regime='bound_only' requires observed_bound",
            ))
    return findings


def validate_independence_semantics(web: EpistemicWeb) -> list[Finding]:
    """Groups must have consistent back-refs. Every pair needs separation basis."""
    findings: list[Finding] = []

    # Check group membership consistency
    for gid, group in web.independence_groups.items():
        for pid in group.member_predictions:
            pred = web.predictions.get(pid)
            if pred is None:
                continue
            if pred.independence_group != gid:
                findings.append(Finding(
                    Severity.CRITICAL,
                    f"independence_groups/{gid}",
                    f"Prediction {pid} listed but doesn't back-reference this group",
                ))

    # Check pairwise separation completeness
    group_ids = sorted(web.independence_groups.keys())
    seen_pairs: set[tuple[str, str]] = set()
    for ps in web.pairwise_separations:
        pair = (min(ps.group_a, ps.group_b), max(ps.group_a, ps.group_b))
        seen_pairs.add(pair)

    for i, a in enumerate(group_ids):
        for b in group_ids[i + 1:]:
            pair = (min(a, b), max(a, b))
            if pair not in seen_pairs:
                findings.append(Finding(
                    Severity.CRITICAL,
                    "independence_groups/pairwise_separation_basis",
                    f"Missing pairwise separation for ({a}, {b})",
                ))

    return findings


def validate_coverage(web: EpistemicWeb) -> list[Finding]:
    """Check for verification gaps."""
    findings: list[Finding] = []

    for cid, claim in web.claims.items():
        if claim.category == "numerical" and not claim.analyses:
            findings.append(Finding(
                Severity.INFO,
                f"claims/{cid}",
                "Numerical claim lacks analysis",
            ))

    for aid, assumption in web.assumptions.items():
        if assumption.type == "E" and not assumption.falsifiable_consequence:
            findings.append(Finding(
                Severity.WARNING,
                f"assumptions/{aid}",
                "Empirical [E] assumption has no falsifiable consequence",
            ))

    stressed = [
        pid for pid, p in web.predictions.items()
        if p.status.value == "STRESSED"
    ]
    if stressed:
        findings.append(Finding(
            Severity.WARNING,
            "predictions",
            f"STRESSED predictions requiring vigilance: {stressed}",
        ))

    return findings


def validate_all(web: EpistemicWeb) -> list[Finding]:
    """Run all domain validators."""
    return (
        validate_tier_constraints(web)
        + validate_independence_semantics(web)
        + validate_coverage(web)
    )
```

**Principles:**
- **Open/Closed**: Add new validators as new functions. `validate_all` is the
  composition point.
- **DRY**: Each rule exists once.
- **Polymorphism**: All validators have signature `(EpistemicWeb) -> list[Finding]`.

### 5.5 Ports (`epistemic/ports.py`)

```python
"""Abstract interfaces the domain REQUIRES but does not IMPLEMENT.

Implemented by the adapters layer. Domain code programs against these
protocols, never against concrete classes.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .types import Finding
from .web import EpistemicWeb


class WebRepository(Protocol):
    """Load and save the epistemic web."""
    def load(self) -> EpistemicWeb: ...
    def save(self, web: EpistemicWeb) -> None: ...


class WebRenderer(Protocol):
    """Generate human-readable artifacts from the web."""
    def render(self, web: EpistemicWeb) -> dict[str, str]:
        """Return {relative_path: content} for all generated surfaces."""
        ...


class WebValidator(Protocol):
    """Validate the web and return findings."""
    def validate(self, web: EpistemicWeb) -> list[Finding]: ...


class ProseSync(Protocol):
    """Update managed prose blocks derived from canonical state."""
    def sync(self, web: EpistemicWeb) -> dict[str, object]: ...


class TransactionLog(Protocol):
    """Append provenance for gateway mutations and queries."""
    def append(self, operation: str, identifier: str) -> str: ...


@dataclass
class ExecutionResult:
    exit_code: int
    stdout: str
    stderr: str


class ResultRecorder(Protocol):
    """Execute a analysis in a controlled environment."""
    def execute(
        self, script_id: str, command: str, **policy: object
    ) -> ExecutionResult: ...
```

**Principles:**
- **Dependency Inversion**: Domain defines what it needs. Infrastructure
  conforms.
- **Interface Segregation**: Each port is as narrow as possible. Read-only
  consumers only need `load()`.

### 5.6 Phase 1 Deliverables and Tests

| Step | What | Tests |
|------|------|-------|
| 1.1 | `epistemic/types.py` — IDs, enums, Finding | Enum membership, Finding construction |
| 1.2 | `epistemic/model.py` — All entity dataclasses, including `Parameter` | Construction, field defaults; verify `Parameter` round-trips value/unit/uncertainty |
| 1.3 | `epistemic/web.py` — EpistemicWeb with register methods | Happy path: register each entity type |
| 1.4 | `epistemic/web.py` — Rejection cases | Duplicate ID, broken reference, cycle detection |
| 1.5 | `epistemic/web.py` — Bidirectional links | claim→assumption.used_in_claims; claim→analysis.claims_covered; prediction→assumption.tested_by; analysis→parameter.used_in_analyses |
| 1.6 | `epistemic/web.py` — Lineage queries | claim_lineage, assumption_lineage on multi-level graphs |
| 1.7 | `epistemic/invariants.py` — All validators | Build webs with known violations, assert findings |
| 1.8 | `epistemic/ports.py` — Protocol definitions | No tests (type definitions only) |

**Target: ~80 tests. All pure Python, no I/O, run in milliseconds.**

Example test session after Phase 1:

```python
from epistemic.domain.web import EpistemicWeb
from epistemic.domain.model import Assumption, Claim
from epistemic.domain.types import AssumptionId, ClaimId

web = EpistemicWeb()
web = web.register_assumption(Assumption(
    id=AssumptionId("A-001"),
    statement="The gauge group is compact and simple",
    type="P", scope="global",
))
web = web.register_claim(Claim(
    id=ClaimId("C-001"),
    statement="Particle spectrum follows from E8 structure",
    type="P", scope="global",
    falsifiability="Predict wrong particle masses",
    assumptions={AssumptionId("A-001")},
))
# A-001.used_in_claims is now {"C-001"} — maintained automatically
assert ClaimId("C-001") in web.assumptions[AssumptionId("A-001")].used_in_claims
```

### Phase 1 Exit Criteria

- [ ] All entity types constructable with native Python types
- [ ] Every register method enforces referential integrity
- [ ] Bidirectional links maintained on register for all five pairs
- [ ] Cycle detection on claim.depends_on works
- [ ] All invariant validators return correct findings
- [ ] Zero imports from outside stdlib

---

## 6. Phase 2 — Persistence, Testing, and Packaging

**Goal:** The domain model can load/save the same JSON files the current
Horizon system uses. The package is installable. Tests cover round-trips.

### 6.1 JSON Repository (`adapters/json_repository.py`)

Reads and writes the flat JSON files from `project/data/`. Handles the
current schema shapes (`claims/v1`, `predictions/v2`, etc.).

```python
"""Flat-JSON persistence adapter.

Implements WebRepository. Reads the same file structure as the current
Horizon system for backward compatibility.
"""
from __future__ import annotations

import json
from pathlib import Path

from ..epistemic.model import Analysis, Assumption, Claim, Prediction, ...
from ..epistemic.ports import WebRepository
from ..epistemic.types import ClaimId, AssumptionId, ...
from ..epistemic.web import EpistemicWeb


class JsonFileRepository:
    """Load/save the epistemic web from flat JSON files on disk."""

    def __init__(self, data_dir: Path) -> None:
        self._data_dir = data_dir

    def load(self) -> EpistemicWeb:
        # Constructs EpistemicWeb directly from JSON dicts, bypassing the
        # register_* mutation methods. This is intentional: load() restores
        # a previously validated and persisted state, not an untrusted
        # payload. Consequence: bidirectional links must be correct in the
        # JSON (the gateway ensures this on every save). If the JSON was
        # manually edited and links are inconsistent, validate() will catch
        # it. Add parameters here when Parameter persistence is implemented.
        return EpistemicWeb(
            claims=self._load_claims(),
            assumptions=self._load_assumptions(),
            predictions=self._load_predictions(),
            scripts=self._load_scripts(),
            independence_groups=self._load_independence_groups(),
            hypotheses=self._load_hypotheses(),
            discoveries=self._load_discoveries(),
            failures=self._load_failures(),
            concepts=self._load_concepts(),
            parameters=self._load_parameters(),
            pairwise_separations=self._load_pairwise_separations(),
        )

    def save(self, web: EpistemicWeb) -> None:
        self._save_claims(web.claims)
        self._save_assumptions(web.assumptions)
        # ... each entity type

    def _load_claims(self) -> dict[ClaimId, Claim]:
        raw = self._read_json("claims.json")
        return {
            ClaimId(k): Claim(
                id=ClaimId(k),
                statement=v["statement"],
                type=v["type"],
                scope=v["scope"],
                falsifiability=v["falsifiability"],
                category=v.get("category", "qualitative"),
                assumptions={AssumptionId(a) for a in v.get("assumptions", [])},
                depends_on={ClaimId(d) for d in v.get("depends_on", [])},
                analyses={AnalysisId(s) for s in v.get("analyses", [])},
            )
            for k, v in raw.get("claims", {}).items()
        }

    def _read_json(self, filename: str) -> dict:
        path = self._data_dir / filename
        if not path.exists():
            return {}
        return json.loads(path.read_text())

    def _write_json(self, filename: str, data: dict) -> None:
        path = self._data_dir / filename
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
```

### 6.2 In-Memory Repository

```python
"""In-memory repository for tests. No disk I/O."""

class InMemoryRepository:
    def __init__(self, web: EpistemicWeb | None = None) -> None:
        self._web = web or EpistemicWeb()

    def load(self) -> EpistemicWeb:
        return self._web

    def save(self, web: EpistemicWeb) -> None:
        self._web = web
```

**Liskov Substitution**: `InMemoryRepository` and `JsonFileRepository` are
interchangeable. Tests use in-memory. Production uses JSON.

### 6.3 Packaging

```toml
[project]
name = "horizon-research"
version = "0.2.0"
requires-python = ">=3.12"
dependencies = [
    "click>=8.1,<9",
    "rich>=13,<14",
]

[project.scripts]
horizon = "horizon_research.interfaces.cli.main:main"

[project.optional-dependencies]
mcp = ["fastmcp>=2,<3"]
compute = ["numpy>=2.4,<3", "scipy>=1.17,<2"]
dev = ["pytest>=8.3,<9", "pytest-cov>=6,<7", "ruff>=0.11,<0.12"]
```

Core package depends only on `click` (CLI framework) and `rich` (terminal
output). These two libraries directly improve the user experience — every
`horizon` command benefits from better argument parsing and beautiful output.
Compute libraries are opt-in for analysiss that need them.

Use `horizon_research` as the public and internal package root. The stable
contract is the `horizon_research` import root plus the `horizon` console
script; `epistemic/` stays nested inside that package as the kernel rather
than becoming the package root.

```python
# src/horizon_research/__main__.py
from horizon_research.interfaces.cli.main import main


if __name__ == "__main__":
    raise SystemExit(main())
```

This keeps `python -m horizon_research` and the console-script entrypoint
stable while the internal subpackages evolve.

Packaging contracts should be tested as code, not left implicit in prose:

- `pyproject.toml` declares the public console scripts and extras
- `horizon_research.__main__` supports `python -m horizon_research`
- coverage settings and workflow artifact expectations are locked by tests
- editable-install smoke tests happen in Phase 2; wheel and sdist smoke tests
    become mandatory by the Phase 4 exit criteria

### 6.4 Public Python API

`horizon_research` is a normal importable package, not just a CLI tool.
Programmers who want to integrate Horizon into notebooks, pipelines, or
custom agents should be able to do so without going through the CLI or MCP:

```python
from horizon_research.controlplane.context import build_project_context
from horizon_research.controlplane.gateway import Gateway
from horizon_research.adapters.json_repository import JsonRepository

ctx = build_project_context(Path("/path/to/workspace"))
repo = JsonRepository(ctx.paths.data_dir)
gateway = Gateway(ctx, repo, ...)

result = gateway.register("claim", {"id": "C-001", "statement": "...", ...})
assert result.status == "ok"
```

The public surface is the `controlplane` layer (Gateway, context builders,
read-only service functions) plus the `epistemic` types and model. Adapters
are public but considered infrastructure — programmers using the package
should code to the ports (`WebRepository`, `ResultRecorder`) not the adapters.

Document this in the quickstart guide (Phase 5) and `__init__.py` re-exports.
The `horizon_research/__init__.py` should re-export the most common entry
points so users don't have to memorize subpackage paths:

```python
# horizon_research/__init__.py
from .controlplane.context import build_project_context as build_context
from .controlplane.gateway import Gateway
from .epistemic.model import Claim, Prediction, Assumption
from .epistemic.types import ClaimId, PredictionId
```

### 6.5 Phase 2 Deliverables

| Step | What | Tests |
|------|------|-------|
| 2.1 | `adapters/json_repository.py` — load all entity types from JSON, including `Parameter` | Round-trip: construct web → save → load → compare; verify Parameter value/unit/uncertainty survive round-trip |
| 2.2 | Schema evolution — handle v1/v2 JSON variants | Load v1 fixture, assert correct domain objects |
| 2.3 | `InMemoryRepository` | Already trivial — verify protocol compliance |
| 2.4 | `pyproject.toml` + `src/horizon_research/` package — installable product boundary | `pip install -e .`, console-script smoke, `python -m horizon_research` |
| 2.5 | Contract tests for packaging, config, and workflow surfaces | Parse `pyproject.toml`, default paths, coverage settings, workflow artifact contract |
| 2.6 | Schema versioning — add `_schema_version` top-level key to every JSON data file | Loader asserts version presence; migration registry maps `(from, to, transform_fn)` per resource type |
| 2.7 | `adapters/markdown_renderer.py` — stub; renders entity summaries to markdown | Snapshot test for claims, predictions, analyses |

### Phase 2 Exit Criteria

- [ ] `JsonRepository` can load and save all entity types
- [ ] Save→load round trip produces identical domain objects
- [ ] Package installs cleanly with `pip install -e .`
- [ ] Public console scripts and `python -m horizon_research` are stable
- [ ] Packaging/config/workflow contracts are locked by tests
- [ ] Every JSON data file carries `_schema_version`; migration registry exists even if empty

---

## 7. Phase 3 — Gateway and Control-Plane Services

**Goal:** Build the product layer that makes Horizon a control plane again:
`ProjectContext`, a typed gateway, read-only services, and the explicit write
transaction boundary.

This phase is where the rebuild stops looking like a domain library and starts
looking like Horizon.

### 7.1 ProjectContext (`config.py`)

Implement the runtime contract first. The control plane should build one
`ProjectContext` and thread it through gateway, validation, rendering, health,
status, and execution services.

```python
def build_project_context(workspace: Path) -> ProjectContext:
    config = load_config(workspace)
    project_dir = workspace / config.project_dir
    paths = ProjectPaths(
        workspace=workspace,
        project_dir=project_dir,
        data_dir=project_dir / "data",
        views_dir=project_dir / "views",
        knowledge_dir=project_dir / "knowledge",
        integrity_dir=project_dir / "integrity",
        verify_script_dir=project_dir / "src" / "verify",
        analysis_script_dir=project_dir / "src" / "analysis",
        cache_dir=project_dir / ".cache",
        render_cache_file=project_dir / ".cache" / "render.json",
        check_refs_cache_file=project_dir / ".cache" / "check_refs.json",
        query_transaction_log_file=project_dir / "logs" / "query_transactions.jsonl",
    )
    return ProjectContext(workspace=workspace, config=config, paths=paths)
```

### 7.2 Gateway (`core/gateway.py`)

The gateway becomes the single external mutation and query boundary. The CLI,
future API surfaces, and automation should go through it instead of reaching
straight into the domain or repository.

```python
@dataclass
class GatewayResult:
    status: str
    changed: bool
    message: str
    findings: list[Finding]
    transaction_id: str | None = None


class Gateway:
    """Typed mutation/query boundary for the control plane."""

    def __init__(
        self,
        context: ProjectContext,
        repo: WebRepository,
        validator: WebValidator,
        renderer: WebRenderer,
        prose_sync: ProseSync,
        tx_log: TransactionLog,
    ) -> None:
        self._context = context
        self._repo = repo
        self._validator = validator
        self._renderer = renderer
        self._prose_sync = prose_sync
        self._tx_log = tx_log

    def register_claim(self, claim: Claim, *, dry_run: bool = False) -> GatewayResult:
        old_web = self._repo.load()
        new_web = old_web.register_claim(claim)
        findings = self._validator.validate(new_web)

        if any(f.severity == Severity.CRITICAL for f in findings):
            return GatewayResult(
                status="blocked",
                changed=False,
                message="registration blocked by CRITICAL findings",
                findings=findings,
            )

        if dry_run:
            return GatewayResult(
                status="ok",
                changed=True,
                message=f"dry run: claim {claim.id} would be registered",
                findings=findings,
            )

        self._repo.save(new_web)
        try:
            self._renderer.render(new_web)
            self._prose_sync.sync(new_web)
        except Exception:
            self._repo.save(old_web)
            self._renderer.render(old_web)
            self._prose_sync.sync(old_web)
            raise

        transaction_id = self._tx_log.append("register_claim", claim.id)
        return GatewayResult(
            status="ok",
            changed=True,
            message=f"registered claim {claim.id}",
            findings=findings,
            transaction_id=transaction_id,
        )
```

This preserves the old transactional idea, but in a cleaner way. The old
system needed raw file snapshots. The new system can usually roll back by
restoring the prior web, then rerendering and resyncing from that canonical
source of truth.

### 7.3 Read-Only Services

These remain separate from the gateway even though they all live in the
control-plane layer:

- `validate.py` — orchestrates domain validators plus structural/project
  checks (asset restrictions, repo layout, schemas, cross-references,
  constraints, coverage, prose consistency, scaling policy)
- `render.py` — derives markdown surfaces from canonical state. Uses
  **incremental SHA-256 fingerprinting**: hash each input JSON file, compare
  against a render cache; skip unchanged outputs. `--check` mode compares
  what _would_ be rendered against disk without writing (detects drift).
- `automation.py` — loads the declarative automation graph:
    - `render_outputs` declares source -> renderer -> path mappings
    - `session_close.stale_triggers` declares stale propagation rules
    - unknown renderers or malformed entries fail fast during normalization
    This keeps render/check/close wiring **open for extension, closed for
    modification**.
- `check.py` — four distinct operations:
  - `check-refs` — scan markdown for broken links (incremental, cached)
  - `check-stale` — find predictions stale due to parameter changes
    (driven by `automation_graph.json` rules, not hardcoded domain knowledge)
  - `sync-prose` — update `<!-- BEGIN AUTO:key -->` / `<!-- END AUTO:key -->`
    blocks inside hand-maintained markdown files
  - `verify-prose-sync` — read-only version of sync-prose (reports drift
    without modifying)
- `metrics.py` — pure computation, no I/O, no side effects:
  - `collect_repo_metrics(data)` — active failures, stressed predictions,
    active kill conditions, tier-A evidence
  - `collect_tier_a_evidence_metrics(predictions, groups)` —
    **correlation-aware** count of independent predictions (10 predictions
    from the same formula are weaker than 3 from separate derivation chains).
    Groups by `independence_group`, reports `raw_count`, `group_count`,
    `registry_backed_count`, and per-group details.
- `health.py` — composes validate, render-check, and project-structure checks
- `status.py` — consumes `metrics.py` output, formats for display. Bounded
  by the scaling policy (caps items per section as the project grows).
- `export.py` — bulk eject path

All depend on `ProjectContext`, the domain, and ports — not on the CLI.

### 7.4 The Transaction Boundary We Keep

Every write should still follow the same high-level shape:

1. Load canonical state
2. Apply one domain mutation
3. Validate the resulting web
4. Persist canonical state
5. Regenerate derived surfaces
6. Sync managed prose blocks if applicable
7. Append provenance / transaction log entry
8. Roll back to the prior web if downstream steps fail

This is one of the best ideas in the old architecture and should remain
central to the rebuild.

### 7.5 Mutation Provenance from Phase 3

Every gateway mutation (register, set, append, transition) should record
minimal provenance metadata on the affected resource:

```json
{
  "_last_modified": "2026-04-03T14:22:00Z",
  "_modified_by": "cli"
}
```

This is almost free — the gateway already writes JSON. It becomes
enormously valuable for:
- `horizon log claim C-003` (show mutation history per resource)
- Auditing prediction status changes
- Reproducibility claims in papers

Timestamps are sufficient for all provenance needs in the core product.

Do not defer this to Phase 7. The cost of adding provenance at the gateway
level is near zero when the gateway is fresh, and retrofitting it later
requires a migration.

### 7.5 Phase 3 Deliverables

| Step | What | Tests |
|------|------|-------|
| 3.1 | `config.py` — build `ProjectContext` from config | Default/custom project layout tests |
| 3.2 | `core/gateway.py` — typed register/get/list/set/transition/query boundary | Integration tests through InMemoryRepository |
| 3.3 | Gateway rollback semantics | Simulate downstream render/sync failure and assert old web restored |
| 3.4 | `core/validate.py` — validation orchestration | Compare findings with current system on characterization fixtures |
| 3.5 | `core/automation.py` — declarative render + stale-trigger contracts | Normalize automation graph; unknown renderer fails fast |
| 3.6 | `views/render.py` — generated surfaces with incremental SHA-256 cache | Snapshot tests for claims, predictions, assumptions, discoveries; cache hit/miss tests |
| 3.7 | `core/check.py` — check-refs, check-stale, sync-prose, verify-prose-sync | Link scanner, staleness rules (uses `Analysis.uses_parameters` ↔ `Parameter.used_in_analyses`), AUTO marker sync |
| 3.8 | `views/metrics.py` — repo metrics and tier-A evidence counting | Correlation-aware group counting, stressed/active failure summaries |
| 3.9 | `views/status.py`, `views/health.py`, `core/export.py` | Read-model and health tests |
| 3.10 | Transaction / provenance log adapter | Append, rollback, and dry-run behavior tests |
| 3.11 | Mutation provenance — `_last_modified`, `_modified_by` on every gateway write | Write + read-back; provenance preserved through round-trip |

**Target: ~60 additional tests.**

### Phase 3 Exit Criteria

- [ ] Gateway is the single mutation/query boundary used by both MCP and CLI
- [ ] `GatewayResult` is the stable result contract for all operations
- [ ] Full register → validate → render → sync → log pipeline works end-to-end
- [ ] Downstream failures restore prior canonical state cleanly
- [ ] Dry-run returns the same result envelope without persisting
- [ ] Read-only services run from explicit `ProjectContext`
- [ ] Render outputs and stale triggers come from declarative automation config
- [ ] Markdown output matches current Horizon behavior for the same data
- [ ] Every gateway write records `_last_modified` and `_modified_by` provenance
- [ ] `check_stale` uses `Analysis.uses_parameters` to identify stale predictions after parameter changes

---

## 8. Phase 4 — MCP, CLI, Init, Health

**Goal:** The product is usable by AI agents over MCP (primary) and by
humans over the CLI (secondary). New users — human or agent — can initialize
a project, register artifacts, validate, and check health.

### 8.1 Shared Result Envelope

Every operation — MCP tool call or CLI command — returns the same result
contract. This is the single most important interface decision in Phase 4:
MCP and CLI are two presentations of the same operation, not two separate
implementations.

`GatewayResult` is defined once in `core/gateway.py` (see section 3.5).
Reproduced here for reference:

```python
@dataclass
class GatewayResult:
    status: str          # "ok" | "error" | "CLEAN" | "BLOCKED" | "dry_run"
    changed: bool
    message: str
    findings: list[Finding]
    transaction_id: str | None = None
    data: dict | None = None  # resource data for get/list/query results
```

JSON envelope (serialized from `GatewayResult`):

```json
{
  "status": "ok" | "error" | "CLEAN" | "BLOCKED" | "dry_run",
  "changed": true | false,
  "message": "...",
  "findings": [...],
  "transaction_id": "...",
  "data": { ... }
}
```

All consumers — agents via MCP, scripts via CLI `--json`, integration tests
— parse `result["status"]` first and branch on it. This contract cannot
change without a version bump.

### 8.2 MCP Server (`interfaces/mcp/server.py`, `interfaces/mcp/tools.py`)

The MCP server is the primary external interface. It exposes the full
control-plane gateway as MCP tools. Agents can register research artifacts,
query the epistemic web, validate, render, and check health — all through
structured tool calls with no subprocess or file manipulation needed.

**Design rules:**
- `interfaces/mcp/tools.py` contains one handler per tool. Each handler is a thin
  wrapper that calls the same gateway or service function the CLI calls.
- No business logic lives in `interfaces/mcp/`. If a handler does more than parse
  inputs + call the control plane + return the result, move the logic up.
- Input schemas are typed cleanly so agents see required/optional fields.
- All results use the shared `GatewayResult` envelope, serialized to JSON.

**MCP tool surface:**

| Tool | Service Call | Read/Write |
|------|-------------|------------|
| `validate_web` | `validate.validate_project(context, repo)` | Read |
| `health_check` | `health.run_health_check(context, repo, validator)` | Read |
| `project_status` | `status.get_status(context, repo)` | Read |
| `get_resource` | `gateway.get(resource_type, id)` | Read |
| `list_resources` | `gateway.list(resource_type)` | Read |
| `register_resource` | `gateway.register(resource_type, payload, dry_run)` | Write |
| `set_resource` | `gateway.set(resource_type, id, payload, dry_run)` | Write |
| `transition_resource` | `gateway.transition(resource_type, id, status, dry_run)` | Write |
| `query_web` | `gateway.query(query_type, **params)` | Read |
| `render_views` | `render.render_all(context, force)` | Write |
| `check_stale` | `check.check_stale(context)` | Read |
| `check_refs` | `check.check_refs(context)` | Read |
| `export_web` | `export.export_json / export_markdown` | Read |

**MCP server entry point** (`interfaces/mcp/server.py`):

```python
def build_server(context: ProjectContext) -> MCPServer:
    """Wire the MCP server to the control-plane gateway."""
    repo = JsonFileRepository(context.paths.data_dir)
    gateway = build_gateway(context, repo)
    server = MCPServer(name="horizon-research")
    register_tools(server, context, gateway)
    return server


def main() -> None:
    context = build_project_context(Path.cwd())
    server = build_server(context)
    server.run()
```

**MCP tool handler shape** (`interfaces/mcp/tools.py`):

```python
def tool_register(
    gateway: Gateway,
    resource_type: str,
    payload: dict,
    dry_run: bool = False,
) -> dict:
    result = gateway.register(resource_type, payload, dry_run=dry_run)
    return asdict(result)
```

**Dependency:** The MCP server depends on `fastmcp` (or an equivalent
stdlib-compatible MCP library). Add it to `[project.optional-dependencies]`
under `[mcp]` — not to the core install — so the package installs without
MCP in environments where it isn't needed.

```toml
[project.optional-dependencies]
mcp = ["fastmcp>=2,<3"]
```

**`pyproject.toml` console-script entry point:**

```toml
[project.scripts]
horizon = "horizon_research.interfaces.cli.main:main"
horizon-mcp = "horizon_research.interfaces.mcp.server:main"
```

### 8.3 CLI (`interfaces/cli/main.py`, `interfaces/cli/formatters.py`)

The CLI is a peer interface alongside MCP — the human and scripting surface. It
wraps the same gateway and service calls as the MCP server, with two output
modes: human-readable (default) and `--json` (same `GatewayResult` envelope
the MCP server returns).

**CLI dispatch table** — every command is one control-plane call:

| Command | Service Call | Read/Write |
|---------|-------------|------------|
| `register` | `gateway.register(...)` | Write |
| `get` | `gateway.get(...)` | Read |
| `list` | `gateway.list(...)` | Read |
| `set` | `gateway.set(...)` | Write |
| `transition` | `gateway.transition(...)` | Write |
| `validate` | `validate.validate_project(context, repo)` | Read |
| `health` | `health.run_health_check(context, repo, validator)` | Read |
| `status` | `status.get_status(context, repo)` | Read |
| `render` | `render.render_all(context, force)` | Write |
| `export` | `export.export_json / export_markdown` | Read |
| `init` | (inline) | Write |

**CLI entry point** — thin dispatch, nothing more:

```python
def main() -> int:
    command, args = parse_argv(sys.argv)
    context = build_project_context(Path.cwd())
    repo = JsonFileRepository(context.paths.data_dir)
    gateway = build_gateway(context, repo)

    result = dispatch(command, args, context, gateway)
    format_result(result, json_mode=args.json)
    return 0 if result.status not in ("error", "BLOCKED") else 1
```

**Principles:** Single Responsibility — CLI parses input and formats output.
Nothing else. CLI never re-implements control-plane logic.

### 8.4 Configuration and Context (`config.py`)

```python
@dataclass
class HorizonConfig:
    project_dir: Path = Path("project")


def load_config(workspace: Path) -> HorizonConfig:
    """Load from horizon.toml if present, else use defaults."""
    toml_path = workspace / "horizon.toml"
    if toml_path.exists():
        raw = tomllib.loads(toml_path.read_text())
        return HorizonConfig(
            project_dir=Path(raw.get("horizon", {}).get("project_dir", "project")),
        )
    return HorizonConfig()
```

### 8.5 `horizon init`

`horizon init` is the platform onboarding experience, not just a scaffolding
command. It runs interactively, asks two questions, and leaves the project
ready for an AI agent to use immediately.

**Interactive session:**

```
$ horizon init

? Project name: quantum-gravity-study
? Description (optional):
  Derive the fine structure constant from first principles

✓ Initialized project workspace
✓ Created project/data/project_config.json
✓ Created horizon.toml

Run `horizon health` or connect your AI agent via `horizon-mcp`.
```

**What it creates:**

```
<project_dir>/
├── data/
│   ├── claims.json
│   ├── assumptions.json
│   ├── predictions.json
│   ├── theories.json
│   ├── discoveries.json
│   ├── analyses.json
│   ├── independence_groups.json
│   ├── dead_ends.json
│   ├── concepts.json
│   ├── parameters.json
│   ├── results.json              ← recorded analysis results (Phase 6)
│   ├── transaction_log.jsonl
│   └── project_config.json      ← project name + description
├── views/
└── .cache/

horizon.toml                ← tool config (project_dir)
```

**`project/data/project_config.json`:**

Project metadata separate from tool configuration (`horizon.toml`).
Holds the project name, description, and any researcher-level annotations.
Mutable via `horizon config set/get` — not a file users need to hand-edit.

```json
{
  "_schema_version": "project_config/v1",
  "name": "quantum-gravity-study",
  "description": "Derive the fine structure constant from first principles"
}
```

Idempotent: safe to run on an existing project. Fills in missing pieces,
never overwrites existing data files.

### 8.6 `horizon health`

Project health check — the "linter for research". Composed from existing
services and exposed as both a CLI command and an MCP tool.

1. Do all data files exist and contain valid JSON?
2. Do all cross-references resolve?
3. Are rendered views current?
4. Are there orphaned resources?
5. Staleness: analyses not re-run after parameter changes
6. Coverage: claims with no analysis, empirical assumptions without testable predictions

Health response:

```json
{
  "status": "HEALTHY",
  "critical": 0,
  "warnings": 2,
  "findings": [...]
}
```

### 8.7 Phase 4 Deliverables

| Step | What | Tests |
|------|------|-------|
| 4.1 | `config.py` — load from horizon.toml with defaults | Config with/without toml, custom project_dir |
| 4.2 | `interfaces/mcp/server.py` + `interfaces/mcp/tools.py` — full core tool surface | Tool calls return correct `GatewayResult` envelopes |
| 4.3 | MCP tool schema parity with CLI `--json` output | Both return identical `GatewayResult` JSON for same operation |
| 4.4 | `horizon-mcp` console-script entry point registered and runnable | Smoke test |
| 4.5 | `interfaces/cli/main.py` — register, get, list, set, transition, validate, health, status, render, export, init | Subprocess tests: check JSON output shape |
| 4.6 | `interfaces/cli/formatters.py` — human + JSON output | Unit tests for formatting |
| 4.7 | `horizon init` | Creates correct directory structure; idempotent |
| 4.8 | `horizon health` (CLI + MCP tool) | Reports known issues in test fixture |
| 4.9 | `horizon export --format=json` | Exports all data as valid JSON |

### Release Checkpoint: First Internal Product Alpha

After Phase 4, an AI agent can:

```
# Via MCP tool calls:
tool: init  args: {}
tool: register  args: {resource_type: "claim", payload: {id: "C-001", ...}}
tool: validate  args: {}
tool: health    args: {}
tool: export    args: {format: "json"}
```

And a human can reach the same operations over the CLI:

```bash
pip install 'horizon-research[mcp]'
horizon init
horizon register claim C-001 '{"statement":"...", "type":"P", ...}'
horizon validate --json
horizon health
```

### Phase 4 Exit Criteria

- [ ] MCP server exposes the full core tool surface
- [ ] MCP tool results and CLI `--json` results share the same `GatewayResult` contract
- [ ] `horizon-mcp` console script entry point is registered and tested
- [ ] CLI dispatches all core commands
- [ ] `horizon init` creates valid project scaffold (idempotent)
- [ ] `horizon health` reports health accurately (CLI + MCP)
- [ ] Both human and JSON CLI output modes work
- [ ] Config is optional (defaults work without horizon.toml)

---

## 9. Phase 5 — Human-First UX

**Goal:** Usable by a researcher who doesn't want to write JSON. The audit
scaffold becomes navigable: a researcher or AI agent can traverse the web,
identify structurally incomplete areas, and audit the chain from any outcome
back to its assumptions.

### 9.1 Deliverables

| # | Feature | Description |
|---|---------|-------------|
| 1 | Pretty-print output | `horizon list claims` shows a Rich table. `--json` for machine output. |
| 2 | `horizon add <type>` | Interactive prompts. Asks required fields one at a time. No JSON. |
| 3 | `horizon show <type> [id]` | Human-readable view with all relationships rendered. `source` shown as clickable link. |
| 4 | `horizon status` | Readable summary with health counts and tier-A evidence summary. |
| 5 | `horizon log [id]` | Mutation history from the transaction log. |
| 6 | Shell completions | Generated for bash, zsh, and fish. Resource ID tab-completion from local data files. |
| 7 | `horizon config set\|get` | Read/write `project_config.json` without editing JSON directly. |
| 8 | Consistent error messages | Actionable hints on all common errors. |
| 9 | Quickstart guide | Install → init → add theory → add claim → add prediction → record result → render. |

For `horizon add prediction`, also prompt for:
- The `specification` — the mathematical relationship or empirical claim being
  tested (human-readable, separate from the analysis). This field
  already exists on the `Prediction` entity from Phase 1.
- The `derivation` — the prose explanation of why the linked claims jointly imply
  this prediction. This is the "why" that an auditor needs to follow the chain.
- The expected value with units

The specification is the **formula contract** and the derivation is the
**reasoning chain** — together they give a reviewer (human or AI agent) everything
needed to audit whether this prediction actually follows from its claims, without
having to re-derive it from first principles.

### 9.2 What This Phase is NOT

- No progressive-disclosure dual CLI. Simple commands (`add`, `show`, `check`)
  coexist with power commands (`register`, `get`, `set`, `query`).
- No `horizon dashboard`. `status` is enough.
- No static HTML rendering. Markdown is fine for now.
- `horizon inspect` reports structural facts about the web. It does not
  suggest new predictions, assess logical correctness, or recommend actions.
  It gives the researcher or agent the map; they do the walking.

### Release Checkpoint: First External Human-Usable Alpha

### Phase 5 Exit Criteria

- [ ] A researcher can use the tool without writing JSON
- [ ] Interactive add works for all core entity types
- [ ] `horizon add prediction` collects specification and derivation prose
- [ ] `horizon show` displays entity with relationships; `source` rendered as link
- [ ] `horizon log` shows per-resource mutation history from provenance data
- [ ] Shell completions generated for bash, zsh, and fish
- [ ] `horizon config set/get` reads and writes `project_config.json` safely
- [ ] Quickstart guide is written and tested end-to-end

---

## 10. Phase 6 — Results Ingestion

**Goal:** Horizon consumes results from analyses the researcher runs in
their own environment. No sandboxing, no execution, no subprocess management.
Horizon records what happened, links it to the epistemic web, and updates
prediction status.

This is the MLflow/W&B model: you instrument your work with a line or two,
and Horizon records the outcome. The computation lives in your tools —
SageMath, Python, R, Jupyter, whatever you trust. Horizon stays focused
on the epistemic layer.

### 10.1 Why Consumer, Not Executor

Running code introduces problems orthogonal to Horizon's core value:

- **Environment management**: dependencies, virtual environments, GPU access,
  OS-specific behaviour — researchers already solve this with their own tooling
- **Security**: sandboxing untrusted code is a hard problem with a long tail
  of failure modes; it is a product in itself
- **Trust**: if Horizon runs the analysis, it owns the result. If the researcher
  runs it, they own the result — which is the correct epistemic relationship

The analyses Horizon tracks are not Horizon's analyses. They belong to the
researcher. Horizon records what they found.

### 10.2 The Recording Model

Three equivalent ways to record a result:

**CLI:**
```bash
horizon record P-007 --value 80.379 --status pass --notes "within 0.1% tolerance"
horizon record P-007 --status fail --notes "derivation has sign error in step 3"
```

**MCP tool (agent workflow):**
```
tool: record_result
args: { prediction_id: "P-007", value: 80.379, status: "pass", notes: "..." }
```

**SDK shim (inline instrumentation):**
```python
# Add two lines to any existing script — your code is otherwise unchanged
from horizon_research import record

result = derive_fine_structure_constant()
record(prediction="P-007", value=result, status="pass")
```

The SDK shim is optional and thin — it calls the same gateway endpoint as
the CLI and MCP tool. No new dependencies, no magic.

### 10.3 What Gets Recorded

`record_result` writes to the transaction log and optionally transitions the
prediction status:

```python
@dataclass
class AnalysisResult:
    prediction_id: PredictionId
    analysis_id: AnalysisId | None      # which analysis produced this
    value: Any                           # the computed/observed value
    status: str                          # "pass" | "fail" | "inconclusive"
    uncertainty: Any = None              # absolute uncertainty on value, same type as value
    git_sha: str | None = None           # auto-captured by `horizon record` if workspace is a git repo
    parameter_snapshot: dict | None = None  # values of Analysis.uses_parameters at record time
    source: str | None = None            # explicit source pointer if not a git-tracked analysis
    notes: str | None = None
    recorded_at: str = ""                # ISO timestamp, set by gateway
```

The gateway records the result to the transaction log and transitions the
prediction status: `pass` maps to `CONFIRMED`, `fail` maps to `REFUTED`
(unless `--no-transition` is passed). The standard `GatewayResult` envelope
is always returned.

### 10.4 Phase 6 Deliverables

| Step | What | Tests |
|------|------|-------|
| 6.1 | `core/results.py` — `record_result(context, prediction_id, value, status, uncertainty, notes, dry_run)` | Records to `data/results.json`; transitions prediction status correctly |
| 6.2 | `adapters/results_repository.py` — load/save `AnalysisResult` list from `data/results.json` | Round-trip; multiple results per prediction preserved in order |
| 6.3 | `horizon record <prediction_id>` CLI command | `--value`, `--uncertainty`, `--status`, `--notes`, `--no-transition`, `--json` flags work |
| 6.4 | `record_result` MCP tool | Returns correct `GatewayResult` envelope |
| 6.5 | `horizon_research.record()` SDK shim | Callable from any Python script; delegates to gateway |
| 6.6 | `core/export.py` — `export_json`, `export_markdown` | Exports include recorded results alongside predictions |
| 6.7 | `horizon results <prediction_id>` — show result history | Loads from `data/results.json`; shows value, uncertainty, status, git_sha, timestamp |
| 6.8 | Git SHA auto-capture in `horizon record` | Captured from `git rev-parse HEAD`; warns if analysis `path` has uncommitted changes |
| 6.9 | `parameter_snapshot` auto-capture in `record_result` | Reads current values of `Analysis.uses_parameters` from web at record time; stored in `AnalysisResult.parameter_snapshot`; round-trips through JSON |

### Phase 6 Exit Criteria

- [ ] A researcher can record a result with one CLI command
- [ ] An agent can record a result with one MCP tool call
- [ ] A Python script can report a result with one SDK line
- [ ] `AnalysisResult` persists to `data/results.json`, not just the transaction log
- [ ] Uncertainty is recorded alongside value for numerical results
- [ ] Prediction status transitions automatically on record (unless suppressed)
- [ ] Result history is visible via `horizon results <id>`
- [ ] Export includes recorded results
- [ ] `horizon record` warns when analysis file has uncommitted changes at record time
- [ ] `parameter_snapshot` captures values of all parameters used by the linked analysis at record time


---

## 11. Backlog

Everything below is real and valuable but not on the critical path for Phase 1–6.

- Schema versioning + `horizon migrate`
- `horizon export --format=csv|notebook|bibtex`
- `horizon import` from BibTeX/CSV
- Research graph traversal — `horizon trace`, `horizon impact`
- Example projects (`examples/` shipped with the package)
- `horizon resolve-conflicts` — JSON-structure-aware merge for multi-user scenarios
- Static HTML rendering — `horizon render --format=html`
- `horizon health` as a CI exit code
- One-file-per-resource layout for multi-user scalability
- Web UI (read-only dashboard over the MCP server)
- VSCode extension
- Pre-registration export (OSF format)

---

## 13. Principle Compliance Matrix

| Principle | How It's Followed | Where |
|-----------|-------------------|-------|
| **Reuse/Release Equivalence (REP)** | The public release boundary is `horizon_research`; the kernel lives in `horizon_research.epistemic`, and internal modules can change behind that stable root without changing console scripts | Phase 2 packaging |
| **S — Single Responsibility** | Each module has exactly one reason to change | `web.py` (graph rules), `core/gateway.py` (transaction boundary), `json_repository.py` (serialization), `interfaces/cli/main.py` (parsing) |
| **O — Open/Closed** | New validators = new functions, not modifications. New entity types = new classes. | `invariants.py`, `model.py` |
| **L — Liskov Substitution** | `InMemoryRepository` and `JsonFileRepository` interchangeable | `ports.py`, all adapters |
| **I — Interface Segregation** | `WebRepository` has only `load()` and `save()`. `ResultRecorder` is separate. | `ports.py` |
| **D — Dependency Inversion** | Domain defines protocols. Adapters implement them. Core depends on abstractions. | `ports.py`, `core/gateway.py` |
| **Low Coupling** | Kernel code has zero imports from adapters or interfaces | Package DAG: `interfaces/* → views → core → adapters → epistemic` |
| **High Cohesion** | `epistemic/` = kernel reasoning. `core/` = mutation/query boundary. `views/` = composed summaries. `adapters/` = I/O. `interfaces/*` = UI. | Package layout |
| **Common Closure (CCP)** | Modules that change together are packaged together: automation/render/check, results ingestion | `core/`, `views/` |
| **Common Reuse (CRP)** | Optional extras (MCP, compute) stay separate from the core install | Package layout, optional extras |
| **DRY** | Bidirectional links maintained once (web mutations). Validation rules each exist once. | `web.py`, `invariants.py` |
| **KISS** | Plain dataclasses, native Python types, `dict`/`set`/`list`. No metaclasses. Dependencies only at CLI/MCP boundaries where they directly improve UX. | Entire codebase |
| **YAGNI** | No plugin system, no event bus, no database, no web server, no generic graph engine. Dependencies earn their place by improving end-user experience, not developer convenience. | Explicit in Phase 1-7 scope limits |
| **Separation of Concerns** | Structural invariants (mutation-time) vs semantic validation (on-demand) vs persistence vs rendering vs UI | Layer architecture |
| **Convention over Configuration** | Default `project/` layout and minimal `horizon.toml`; declarative automation graph only for the places that truly vary | `config.py`, `core/automation.py` |
| **Principle of Least Privilege** | Execution defaults to no network, no subprocess, no writes outside declared roots; CI defaults to read-only permissions except release jobs | ``, `adapters/results.py`, CI/CD rollout |
| **Law of Demeter** | Entities hold IDs, not objects. Traverse through `EpistemicWeb` methods. | `model.py`, `web.py` |
| **Composition over Inheritance** | No entity inherits from another. Protocols for interfaces, not abstract base classes. | `model.py`, `ports.py` |
| **Encapsulation** | All invariant enforcement inside `EpistemicWeb`. External code uses methods, not direct mutation. | `web.py` |
| **Abstraction** | External code sees `web.register_claim()`, not back-reference bookkeeping. | `web.py` |
| **Polymorphism** | All validators: `(Web) -> list[Finding]`. All repos: `WebRepository` protocol. | `invariants.py`, `ports.py` |
| **Fail Fast** | Domain throws on broken refs/cycles. Don't wait for post-hoc validation. | `web.py` |
| **Acyclic Dependencies (ADP)** | `interfaces/* → features → views → core → adapters → epistemic`. No cycles. | Package DAG |
| **Stable Dependencies (SDP)** | `epistemic/` (most stable) ← everything else. `interfaces/*` (least stable) → all layers below. | Package DAG |
| **Stable Abstractions (SAP)** | Stable packages define protocols and normalized contracts; unstable packages stay concrete and close to I/O | `epistemic/ports.py`, `core/automation.py`, `interfaces/*`, `adapters/` |

---

## 14. Clean Break from the Current Codebase

### 14.1 Why Not Migrate

The current codebase proved the domain model. It did its job. But the wiring
is fundamentally broken — module-level globals, monkey-patching, circular
dependencies resolved at runtime. Trying to incrementally refactor this into
the right architecture would mean:

1. Writing characterization tests around fragile wiring we plan to delete
2. Threading two architectures through every module simultaneously
3. Debugging subtle behavioral differences between old and new code paths
4. Carrying legacy patterns forward "temporarily" until they become permanent

That is exactly how codebases rot. The domain model is correct. The wiring
is not. Build the right thing from scratch.

### 14.2 What We Take Forward

**Ideas, not code:**

| What | How It Carries Forward |
|------|----------------------|
| Domain vocabulary (claims, assumptions, predictions, independence groups) | Rebuilt as typed entities in `epistemic/model.py` |
| Gateway as single mutation boundary | Rebuilt as `core/gateway.py` with typed contracts |
| Transactional write → validate → render → rollback | Same pipeline, clean implementation |
| Declarative automation graph | Same config format, clean loader |
| Sandbox execution model | Same deny-by-default philosophy, clean executor |
| Bidirectional invariants | Enforced at mutation time instead of validated after the fact |
| Incremental rendering (SHA-256 fingerprints) | Same caching strategy, clean I/O |
| JSON file format | Same schema, read by new `JsonFileRepository` |

**Nothing** from `src/horizon_core/` or `src/horizon.py` is imported,
subclassed, or wrapped. The new `src/horizon_research/` package is a
standalone implementation that happens to read the same JSON format.

### 14.3 Transition Plan

1. Build `src/horizon_research/` as a new package tree
2. Old code stays in the repo untouched during development
3. New tests validate against the JSON schema, not against old code behavior
4. When the new system reaches Phase 4 (CLI + MCP working), delete the old
   code entirely
5. No coexistence period, no gradual migration, no behavioral equivalence
   tests against the old system

### 14.4 What About Existing Project Data?

The JSON data files in `project/data/` are the single source of truth. The
new `JsonFileRepository` reads the same JSON format the old system wrote.
If the new system can load, validate, render, and round-trip those files
correctly, the transition is complete. The data survives; the code doesn't.

---

## 15. Standing Decisions

- Horizon is rebuilt as a **control plane** over a project **data plane**.
- The gateway remains the single mutation/query boundary.
- This is a **clean-break rebuild**, not an incremental migration. Ideas
  carry forward; code does not.
- New projects are core-only by default.
- Governance (sessions, boundaries, close gates) is opt-in, off by default,
  but designed-in from Phase 3 as a first-class capability.
- Literature watch is opt-in, off by default.
- Agent config is opt-in, not shipped by default.
- Network access is off by default.
- Import paths are offline-first: local file parsing always works; online
  fetch is opt-in with explicit network permission.
- Git integration is for results ingestion only: `horizon record` captures the
  git SHA at record time. Core operations never require git. Horizon works for
  researchers using Dropbox, OneDrive, or a plain local folder.
- Distribution name: `horizon-research`.
- Import namespace: `epistemic` (internal), `horizon_research` (public).
- Primary CLI: `horizon`.
- Optional CLI alias: `horizon-research`.
- Declarative automation graph remains the source of truth for generated-output
    wiring and stale-trigger propagation.
- Mutation provenance (`_last_modified`, `_modified_by`) ships in Phase 3
    with the gateway.
- Packaging, config, and workflow contracts should be tested as code.
- Flat JSON files. Reconsider only if merge conflicts become a real problem.
- Native Python types (`dict`, `set`, `list`) in the domain model.
- Domain core (`epistemic/`), `core/`, and `views/` are stdlib only.
  `interfaces/cli/` uses `click` and `rich` for a professional UX.
  `interfaces/mcp/` uses `fastmcp` as an optional extra. Compute deps (`numpy`, `scipy`) are
  optional extras. The dependency tree stays shallow — direct deps only.
- Vocabulary is domain-neutral by design. Entity names, relationship types,
  and invariants apply to any empirical discipline without modification.

---

## 16. Data Flow Diagram

The system has three operational paths — read, write, and execute:

```
                              ┌──────────────────┐
                              │   horizon.toml   │
                              │ (optional config) │
                              └────────┬─────────┘
                                       │
                              ┌────────┴─────────┐
                              │  ProjectContext   │
                              │  (built once)     │
                              └────────┬─────────┘
                                       │
            ┌──────────────────────────┼────────────────────────────┐
            │                          │                            │
    ┌───────┴───────┐         ┌───────┴────────┐          ┌───────┴───────┐
    │  Read Path    │         │  Write Path    │          │ Execute Path  │
    │               │         │                │          │               │
    │ validate      │         │ gateway CRUD   │          │ run-script    │
    │ render --check│         │                │          │               │
    │ status        │         │                │          │               │
    │ check-*       │         │                │          │               │
    └───────┬───────┘         └───────┬────────┘          └───────┬───────┘
            │                         │                           │
            │                    ┌────┴────┐                      │
            │                    │ 1. Write│                      │
            │                    │   JSON  │                      │
            │                    └────┬────┘                      │
            │                         │                           │
            │                    ┌────┴────┐                      │
            │                    │2. Render│                      │
            │                    │  views  │                      │
            │                    └────┬────┘                      │
            │                         │                           │
            │                    ┌────┴────┐                      │
            │                    │3. Sync  │                      │
            │                    │  prose  │                      │
            │                    └────┬────┘                      │
            │                         │                           │
            │                    ┌────┴────┐                      │
            │                    │4. Full  │                      │
            │                    │validate │                      │
            │                    └────┬────┘                      │
            │                         │                           │
            │                    ┌────┴────┐                      │
    ┌───────┴───────┐            │ Pass?   │          ┌───────────┴───────┐
    │  JSON files   │←───────── │ Commit  │          │  verification    │
    │  (canonical)  │  rollback │ or      │          │  scripts (stdout)│
    │               │  on fail  │ rollback│          │                  │
    └───────┬───────┘            └─────────┘          └────────┬────────┘
            │                                                  │
    ┌───────┴───────┐                                ┌────────┴────────┐
    │  Markdown     │                                │  Benchmark      │
    │  (generated)  │                                │  validation     │
    └───────────────┘                                └─────────────────┘
```

**JSON files are the single source of truth.** Every markdown file is derived
from JSON. Every validation operates on JSON. The only way to modify JSON is
through the gateway. Rolling back any operation is "restore the old web and
re-render."

---

## 17. End-to-End Traces

These traces serve as executable specifications — they document_exactly_ how
data flows through the system for the three most common operations.

### 17.1 Trace: `horizon validate --json`

1. **CLI**: parse `sys.argv` → command=`"validate"`, flags: `quick=False`,
   `output_json=True`
2. **Context**: `context = build_project_context(Path.cwd())` — reads
   `horizon.toml` if present, derives all paths, returns frozen
   `ProjectContext`
3. **Service call**: `validate.run_validate(context, quick=False)`
4. **Inside `run_validate`**:
   - `data = repo.load()` — reads JSON files into domain model
   - Run structural validators (asset restrictions, repo layout, schemas)
   - If not quick: run cross-references, constraints, machine-readable checks,
     coverage, prose consistency, scaling policy
   - Each validator returns `list[Finding]`; concatenate all
5. **Output**: JSON envelope `{"status": "CLEAN"|"BLOCKED", "critical": N,
   "warning": N, "info": N, "findings": [...]}`
6. **Exit**: `sys.exit(1 if critical > 0 else 0)`

Module imports: `src/horizon_research/interfaces/cli/main.py` →
`src/horizon_research/core/validate.py` →
`src/horizon_research/epistemic/invariants.py`,
`src/horizon_research/adapters/json_repository.py`. No cycles.

Functions that need paths take `context`. Functions that only analyze
in-memory data take `web` or `data`. Pure validators never touch the
filesystem.

### 17.2 Trace: `horizon register claim C-099 '{...}'`

1. **CLI**: parse → command=`"register"`, resource=`"claim"`, id=`"C-099"`,
   payload=JSON string, optional `--reason`, `--dry-run`, `--json`
2. **Context**: build `ProjectContext`
3. **Gateway entry**: `gateway.register("claim", "C-099", parsed_payload)`
4. **Inside the gateway**:
   1. Resolve `"claim"` → canonical resource key via alias table
   2. Load current web: `old_web = repo.load()`
   3. Build domain entity from parsed payload + register defaults
   4. `new_web = old_web.register_claim(claim)` — enforces refs, no cycles,
      maintains bidirectional links
   5. Validate: `findings = validator.validate(new_web)` — if CRITICAL, return
      `GatewayResult(status="blocked", ...)`
   6. If `--dry-run`: return result without persisting
   7. **Persist**: `repo.save(new_web)`
   8. **Render**: `renderer.render(new_web)` → regenerate affected markdown
   9. **Sync prose**: `prose_sync.sync(new_web)` → update AUTO blocks
   10. If render/sync fails: **rollback** — `repo.save(old_web)`,
       re-render, re-sync from old state
   11. **Log**: `tx_log.append("register_claim", "C-099")` → append to
       `query_transactions.jsonl`
5. **Return**: `GatewayResult(status="ok", changed=True, transaction_id=...)`

The guarantee: after any gateway command, the project is in a *consistent*
state — JSON, rendered markdown, and prose surfaces all agree.

### 17.3 Trace: `horizon run-script SCR-001 --json`

1. **CLI**: parse → command=`"run-script"`, script_id=`"SCR-001"`
2. **Context**: build `ProjectContext`
3. **Script dispatch**: load `analyses.json`, look up `"SCR-001"`, read
   command and execution context
4. **Command normalization**: parse command string, validate target script
   resolves inside workspace (path-traversal protection), bind `python` to
   current interpreter
5. **Build sandbox command**: read execution context
   (`requires_network=false`, `write_paths=[]`, etc.), construct the
   `sandbox_runner.py` invocation with appropriate flags
6. **Execute**: `subprocess.run(sandbox_command, ...)`, capture stdout/stderr
7. **Benchmark validation** (if `machine_readable_output: true`): parse
   structured benchmark data from stdout, validate predicted vs. computed
   values against declared tolerances — independently of script's
   self-reported pass/fail
8. **Return**: `{"status": "PASS"|"FAIL"|"ERROR", "script_id": "SCR-001",
   "backend": "...", "returncode": 0, ...}`

---

## 18. Testing Strategy and Fixture Model

### 18.1 Two Fixture Types

1. **Product fixture:** A minimal project directory created in `tmp_path` for
   each test. Contains only the JSON files needed for the test. No git repo,
   no extra metadata. This is the standard for unit
   and integration tests.

2. **Repo fixture:** Points `ProjectContext` at the real repo layout for
   characterization tests that verify backward compatibility with the
   development environment.

### 18.2 What to Test Where

| Test Type | Uses | Imports |
| --- | --- | --- |
| Domain model unit tests | In-memory only | `src/horizon_research/epistemic/web.py`, `src/horizon_research/epistemic/invariants.py` |
| Repository round-trip tests | Product fixture | `src/horizon_research/adapters/json_repository.py` |
| Validator unit tests | Product fixture | `src/horizon_research/core/validate.py` |
| Renderer snapshot tests | Product fixture | `src/horizon_research/views/render.py` |
| Automation/config contract tests | Parse files as data | `src/horizon_research/core/automation.py`, `pyproject.toml`, workflow files |
| Gateway integration tests | Product fixture + InMemoryRepo | `src/horizon_research/core/gateway.py` |
| Rollback tests | Product fixture | `src/horizon_research/core/gateway.py` |
| CLI integration tests | Repo fixture or subprocess | `src/horizon_research/interfaces/cli/main.py` |
| Config loading tests | Temp dirs | `src/horizon_research/config.py` |
| Limitation/gap tests | Synthetic fixtures | benchmark validators |
| Characterization tests | Repo fixture | Old system + new system comparison |

### 18.3 The Key Property

Every test that uses `ProjectContext` can point it at an arbitrary directory.
No test ever needs to run `_sync_compatibility_state()` or import `horizon.py`
to make core modules work. This is the testability payoff of the rebuild.

Also keep **explicit limitation tests** for known blind spots. If the trust
engine cannot detect an "honest but wrong" verifier yet, that limitation
should live in a named test instead of disappearing into tribal knowledge.

---

## 19. Where to Put New Code

**Decision tree for placement:**

```
Is it parsing sys.argv or formatting CLI output?
    → src/horizon_research/interfaces/cli/main.py, interfaces/cli/formatters.py

Is it an MCP tool handler or FastMCP server wiring?
    → src/horizon_research/interfaces/mcp/server.py, interfaces/mcp/tools.py

Is it resolving paths from config or building ProjectContext?
    → src/horizon_research/config.py

Is it declarative wiring between source data, generated outputs, and stale triggers?
    → src/horizon_research/core/automation.py

Is it CRUD on a resource type, or orchestrating a mutation pipeline?
    → src/horizon_research/core/gateway.py

Is it validating data for correctness?
    → src/horizon_research/core/validate.py (orchestration) or src/horizon_research/epistemic/invariants.py (pure rules)

Is it generating markdown from JSON?
    → src/horizon_research/views/render.py (incremental) or src/horizon_research/adapters/markdown_renderer.py (templates)

Is it computing project health metrics?
    → src/horizon_research/views/metrics.py

Is it checking links, staleness, or prose sync?
    → src/horizon_research/core/check.py

Is it displaying project state or health summaries?
    → src/horizon_research/views/status.py or src/horizon_research/views/health.py

Is it recording analysis results from external tools?
    → src/horizon_research/core/results.py (logic) or src/horizon_research/adapters/results_repository.py (persistence)

Is it archiving/activating research programs?
    → program_manager (outer shell — NOT in the product core)

Is it pure domain logic (entities, invariants, graph queries)?
    → src/horizon_research/epistemic/
```

**The six rules:**

1. If it parses `sys.argv`, it goes in `src/horizon_research/interfaces/cli/`.
2. If it is an MCP tool handler, it goes in `src/horizon_research/interfaces/mcp/`.
3. If it computes paths from config, it goes in `src/horizon_research/config.py`.
4. If it expresses source → output or stale-trigger wiring, it goes in `src/horizon_research/core/automation.py`.
5. If it mutates canonical JSON, it goes through `src/horizon_research/core/gateway.py`.
6. If it only reads data and returns findings, it goes in `src/horizon_research/core/validate.py` or `src/horizon_research/epistemic/invariants.py`.

---

## 20. CI/CD Rollout

CI should start **now**. CD should start only once the install surface is real.

### 20.1 Why CI/CD Belongs in the Plan

For Horizon, CI is not just a unit-test runner. It is an **off-machine audit
surface** that proves a delivered state still satisfies the control-plane
contracts:

- linting and unit/integration tests
- validation of canonical state
- generated-output drift detection
- markdown link integrity
- regression harness coverage for orchestration helpers
- artifact upload of machine-readable results

That model is already correct in the current repo and should survive the rebuild.

### 20.2 When to Set It Up

1. **Immediately, during the rebuild:** keep the existing post-push validation
    workflow on `main`. It protects delivered states while old and new systems
    coexist.
2. **By the end of Phase 1:** add a fast PR workflow for the new pure-domain
    surface. As soon as the domain exists, regressions in it are too expensive
    to catch manually.
3. **By the end of Phase 2:** make PR CI a required merge gate. This is the
    point where packaging, repositories, and characterization tests create a
    credible reusable product boundary.
4. **By the end of Phase 4:** add end-to-end product CI that exercises the
    installable CLI (`horizon init`, register, validate, render, health,
    export). That is the first point where the product is truly distributable.
5. **By the end of Phase 6:** add release automation (build, smoke install,
    publish prereleases/stable tags). Governance is optional and should not
    block package publishing.

### 20.3 Recommended Workflow Set

**`ci-pr.yml`** — fast pre-merge gate

- `ruff check`
- pure-domain and adapter unit tests
- packaging/config/workflow contract tests
- editable-install smoke test
- Linux first; add macOS once execution-path code lands

**`ci-main.yml`** — deeper post-merge audit lane

- full `pytest` with coverage
- `horizon validate --json`
- `horizon scaling --json`
- regression harness / orchestration checks
- `horizon render --check --json`
- `horizon check-refs --all --json`
- `horizon status --json`
- upload a validation bundle artifact (`coverage.xml`, JSON reports,
  workflow metadata)

**`release.yml`** — tag-driven delivery

- build `sdist` + wheel
- create a clean virtualenv and `pip install` the built artifacts
- smoke `horizon version`, `python -m horizon_research version`, and a tiny
  `horizon init` flow
- publish prereleases to TestPyPI first
- publish stable tags to PyPI only after smoke/install checks pass
- attach artifacts and release notes to a GitHub Release

### 20.4 What CI Should Test as Code

Do not rely on documentation to keep the automation honest. Add contract tests
that parse repo files directly and assert:

- `pyproject.toml` declares the expected console scripts and extras
- `horizon_research.__main__` remains functional
- coverage settings keep the right source roots and omit transient sabotage files
- workflow files still emit the expected coverage and validation artifacts
- default config/path contracts remain coherent

This is a good example of **Fail Fast**, **DRY**, and **Convention over
Configuration** applied to the build system itself.

### 20.5 CD Timing Recommendation

- **Now:** CI only. Do not try to publish packages yet.
- **After Phase 4 exit:** start TestPyPI prereleases for internal alpha builds.
- **After Phase 5 exit:** PyPI prereleases are reasonable if the human-first CLI
  is stable enough for external evaluation.
- **After Phase 6 exit:** stable PyPI releases become defensible because the
  execution pipeline, benchmark validation, and least-privilege runtime model
  are part of the shipped product rather than future promises.

If you want the short answer: **set up CI immediately, require PR CI by Phase 2,
start prerelease CD after Phase 4, and do stable release CD after Phase 6.**

---

## Dependency Graph

```
Phase 1 (Domain Core — epistemic web)
  └─► Phase 2 (Persistence + Testing + Packaging)
      └─► Phase 3 (Gateway + Control-Plane Services)
              └─► Phase 4 (CLI + Init + Health)
                    └─► Phase 5 (Human-First UX)
                          └─► Phase 6 (Execution Pipeline)
                                └─► Phase 7 (Governance Opt-In)
                                      └─► Backlog
```

Seven sequential phases. Each ships something testable. Each builds on the
last. The epistemic web is the foundation — get it right, and everything else
falls into place naturally.

---

## What This Plan Optimizes For

1. **Correctness first** — The domain model enforces invariants at every mutation.
   It's impossible to create an inconsistent epistemic web.
2. **Testability** — The domain is pure Python with no I/O. Tests run in
   milliseconds. External dependencies are injected through protocols.
3. **Time to first user** — 4 phases to a usable product.
4. **Each phase ships something real** — No phase is pure infrastructure.
5. **No speculative abstraction** — Plugin systems, event buses, config
   profiles all deferred until there's demand.
6. **Principled architecture** — Every design decision maps to a named
   software engineering principle (see the matrix above).
7. **Clean break** — Build the right thing from scratch. The old codebase
   proved the domain model; the new codebase gets the architecture right.
8. **Great UX** — Targeted dependencies (`click`, `rich`) make the tool
   feel professional and easy to use. Domain-general naming makes it
   accessible to any empirical discipline.
9. **Verification integrity** — Both false positives and false negatives
   are caught through a seven-layer verification pipeline, from static
   analysis through sensitivity testing to dual-implementation checks.

---

## The First 100 Lines You Write

```
1. epistemic/types.py    — ClaimId, AssumptionId, ..., Finding, Severity
2. epistemic/model.py    — Claim, Assumption, Prediction (dataclasses with set/list/dict)
3. epistemic/web.py      — EpistemicWeb with register_claim + invariant checks
4. tests/test_web.py      — 20 tests: register, duplicate, broken ref, cycle
5. epistemic/invariants.py — validate_tier_constraints, validate_coverage
6. tests/test_invariants.py — 10 tests: tier violations, coverage gaps
```

That's Phase 1. Everything else builds on this foundation.ves a delivered state still satisfies the control-plane
contracts:

- linting and unit/integration tests
- validation of canonical state
- generated-output drift detection
- markdown link integrity
- regression harness coverage for orchestration helpers
- artifact upload of machine-readable results

That model is already correct in the current repo and should survive the rebuild.

### 20.2 When to Set It Up

1. **Immediately, during the rebuild:** keep the existing post-push validation
    workflow on `main`. It protects delivered states while old and new systems
    coexist.
2. **By the end of Phase 1:** add a fast PR workflow for the new pure-domain
    surface. As soon as the domain exists, regressions in it are too expensive
    to catch manually.
3. **By the end of Phase 2:** make PR CI a required merge gate. This is the
    point where packaging, repositories, and characterization tests create a
    credible reusable product boundary.
4. **By the end of Phase 4:** add end-to-end product CI that exercises the
    installable CLI (`horizon init`, register, validate, render, health,
    export). That is the first point where the product is truly distributable.
5. **By the end of Phase 6:** add release automation (build, smoke install,
    publish prereleases/stable tags). Governance is optional and should not
    block package publishing.

### 20.3 Recommended Workflow Set

**`ci-pr.yml`** — fast pre-merge gate

- `ruff check`
- pure-domain and adapter unit tests
- packaging/config/workflow contract tests
- editable-install smoke test
- Linux first; add macOS once execution-path code lands

**`ci-main.yml`** — deeper post-merge audit lane

- full `pytest` with coverage
- `horizon validate --json`
- `horizon scaling --json`
- regression harness / orchestration checks
- `horizon render --check --json`
- `horizon check-refs --all --json`
- `horizon status --json`
- upload a validation bundle artifact (`coverage.xml`, JSON reports,
  workflow metadata)

**`release.yml`** — tag-driven delivery

- build `sdist` + wheel
- create a clean virtualenv and `pip install` the built artifacts
- smoke `horizon version`, `python -m horizon_research version`, and a tiny
  `horizon init` flow
- publish prereleases to TestPyPI first
- publish stable tags to PyPI only after smoke/install checks pass
- attach artifacts and release notes to a GitHub Release

### 20.4 What CI Should Test as Code

Do not rely on documentation to keep the automation honest. Add contract tests
that parse repo files directly and assert:

- `pyproject.toml` declares the expected console scripts and extras
- `horizon_research.__main__` remains functional
- coverage settings keep the right source roots and omit transient sabotage files
- workflow files still emit the expected coverage and validation artifacts
- default config/path contracts remain coherent

This is a good example of **Fail Fast**, **DRY**, and **Convention over
Configuration** applied to the build system itself.

### 20.5 CD Timing Recommendation

- **Now:** CI only. Do not try to publish packages yet.
- **After Phase 4 exit:** start TestPyPI prereleases for internal alpha builds.
- **After Phase 5 exit:** PyPI prereleases are reasonable if the human-first CLI
  is stable enough for external evaluation.
- **After Phase 6 exit:** stable PyPI releases become defensible because the
  execution pipeline, benchmark validation, and least-privilege runtime model
  are part of the shipped product rather than future promises.

If you want the short answer: **set up CI immediately, require PR CI by Phase 2,
start prerelease CD after Phase 4, and do stable release CD after Phase 6.**

---

## Dependency Graph

```
Phase 1 (Domain Core — epistemic web)
  └─► Phase 2 (Persistence + Testing + Packaging)
      └─► Phase 3 (Gateway + Control-Plane Services)
              └─► Phase 4 (CLI + Init + Health)
                    └─► Phase 5 (Human-First UX)
                          └─► Phase 6 (Execution Pipeline)
                                └─► Phase 7 (Governance Opt-In)
                                      └─► Backlog
```

Seven sequential phases. Each ships something testable. Each builds on the
last. The epistemic web is the foundation — get it right, and everything else
falls into place naturally.

---

## What This Plan Optimizes For

1. **Correctness first** — The domain model enforces invariants at every mutation.
   It's impossible to create an inconsistent epistemic web.
2. **Testability** — The domain is pure Python with no I/O. Tests run in
   milliseconds. External dependencies are injected through protocols.
3. **Time to first user** — 4 phases to a usable product.
4. **Each phase ships something real** — No phase is pure infrastructure.
5. **No speculative abstraction** — Plugin systems, event buses, config
   profiles all deferred until there's demand.
6. **Principled architecture** — Every design decision maps to a named
   software engineering principle (see the matrix above).
7. **Clean break** — Build the right thing from scratch. The old codebase
   proved the domain model; the new codebase gets the architecture right.
8. **Great UX** — Targeted dependencies (`click`, `rich`) make the tool
   feel professional and easy to use. Domain-general naming makes it
   accessible to any empirical discipline.
9. **Verification integrity** — Both false positives and false negatives
   are caught through a seven-layer verification pipeline, from static
   analysis through sensitivity testing to dual-implementation checks.

---

## The First 100 Lines You Write

```
1. epistemic/types.py    — ClaimId, AssumptionId, ..., Finding, Severity
2. epistemic/model.py    — Claim, Assumption, Prediction (dataclasses with set/list/dict)
3. epistemic/web.py      — EpistemicWeb with register_claim + invariant checks
4. tests/test_web.py      — 20 tests: register, duplicate, broken ref, cycle
5. epistemic/invariants.py — validate_tier_constraints, validate_coverage
6. tests/test_invariants.py — 10 tests: tier violations, coverage gaps
```

That's Phase 1. Everything else builds on this foundation.