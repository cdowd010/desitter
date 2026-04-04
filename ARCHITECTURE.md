# Architecture

This document explains how deSitter works end-to-end: the layer model, the epistemic domain, data flow through the system, key design decisions, and the package dependency rules.

---

## Table of Contents

1. [What deSitter Is](#1-what-desitter-is)
2. [The Layer Cake](#2-the-layer-cake)
3. [The Epistemic Web](#3-the-epistemic-web)
4. [Data Flow: Registering a Claim](#4-data-flow-registering-a-claim)
5. [Data Flow: Health Check](#5-data-flow-health-check)
6. [Package Layout and Dependency Rules](#6-package-layout-and-dependency-rules)
7. [The Gateway](#7-the-gateway)
8. [ProjectContext](#8-projectcontext)
9. [The Adapter Pattern](#9-the-adapter-pattern)
10. [Key Design Decisions](#10-key-design-decisions)
11. [Architecture Remediation Plan](#11-architecture-remediation-plan)
12. [Boundary Test Matrix](#12-boundary-test-matrix)
13. [Scale Strategy For Query Performance](#13-scale-strategy-for-query-performance)

---

## 1. What deSitter Is

### The problem

Research projects accumulate a hidden graph of dependencies between ideas. A claim depends on an assumption. A prediction follows from that claim. An analysis tests that prediction. These relationships exist whether or not you track them — but when they're implicit, they break silently: a refuted prediction doesn't update the claims that rely on it, a changed assumption doesn't propagate, and months later nobody knows why a conclusion was drawn.

**Epistemic** means "relating to knowledge and how it's justified." An **epistemic web** is the explicit, machine-checkable graph of those dependencies: what claims exist, what they depend on, what predictions they make, and what evidence supports or refutes them.

deSitter manages that graph.

### The Audit Scaffold Principle

deSitter is an **audit scaffold**, not a reasoning engine. It surfaces structural facts about the epistemic graph — missing links, untested assumptions, uncovered predictions — and gives researchers and AI agents the navigational structure to do their own reasoning.

**What deSitter does:**
- Records the structure of the epistemic graph
- Enforces referential integrity and bidirectional invariants
- Reports structural observations (`StructuralGap`, `Finding`)
- Exposes a traversal API so agents can navigate the graph

**What deSitter does not do:**
- Make logical judgments about whether a theory is correct
- Prescribe which experiments to run
- Suggest how to fix a structural gap
- Execute analyses (the researcher runs them; deSitter records the results)

This distinction matters. An AI agent calling `get_structural_gaps` gets a list of observations — "Assumption A-003 has a falsifiable consequence but no predictions in `tested_by`" — and applies its own domain knowledge to decide what to do about it. deSitter provides the map. The researcher or agent is the auditor.

### Control plane vs. data plane

- The **data plane** is the project state on disk: canonical JSON registries of claims and predictions, generated markdown views, recorded analysis results. This is the research artifact.
- The **control plane** is the code that manages that data plane: validates consistency, renders views, records results, and exposes everything through a stable API. This is deSitter.
- The **epistemic web** is the in-memory representation of the data plane that the control plane works with — the domain model at the core.

---

## 2. The Layer Cake

### What is MCP?

MCP (Model Context Protocol) is an open standard that lets AI agents (Claude, Cursor, GitHub Copilot, etc.) call typed tools exposed by a server — similar to REST APIs, but designed specifically for AI agent use. Instead of an HTTP request, an agent calls a named tool with structured arguments and gets a structured result back. No subprocess wrangling, no screen scraping.

deSitter's MCP server is the primary interface for AI agents. An agent calls `register_claim(...)` or `run_health_check()` directly as a tool, with full type information and structured responses.

### The layers

```
┌──────────────────────────────────────────────────────┐
│  Interface Layer (interfaces/) — equal peers         │
│  cli/  Humans + scripts       mcp/  AI agents        │
│  rest/ future · gui/ future · sdk/ future            │
└─────────────────────┬────────────────────────────────┘
                      │  (no business logic in any interface)
┌─────────────────────▼────────────────────────────────┐
│  View Services (views/) — always available           │
│  health · render · status · metrics                  │
│  Read-only composed summaries + derived files        │
└─────────────────────┬────────────────────────────────┘
                      │
┌─────────────────────▼────────────────────────────────┐
│  Core Services (controlplane/) — always available            │
│  Mutations:  gateway · results                       │
│  Queries:    validate · check · export               │
│  Policy:     automation (render-trigger table)       │
└─────────────────────┬────────────────────────────────┘
                      │
┌─────────────────────▼────────────────────────────────┐
│  Config (config.py) — runtime contract               │
│  DesitterConfig · ProjectContext · ProjectPaths       │
│  load_config() · build_context()                     │
└─────────────────────┬────────────────────────────────┘
                      │
┌─────────────────────▼────────────────────────────────┐
│  Infrastructure Adapters (adapters/)                 │
│  json_repository · transaction_log                   │
│  markdown_renderer                                   │
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

**Hard dependency rule:** arrows point down only. No layer may import from a layer above it.

```mermaid
graph TD
    IFACE["interfaces/*"] --> VIEWS["views/"]
    IFACE --> CORE["controlplane/"]
    VIEWS --> CORE
    CORE --> ADP["adapters/"]
    CORE --> EPI["epistemic/"]
    ADP --> EPI
    CORE -.->|"through abstract interfaces"| ADP
```

The dashed arrow means `controlplane/` uses adapters only through abstract interfaces defined in `epistemic/ports.py` — it never imports a concrete adapter class directly. Concrete adapters are wired together in the interface layer at startup when the Gateway is constructed.

### Interface layer design

All entry points live under `interfaces/` as equal peers. No interface is primary:

- `interfaces/cli/` — humans and scripts (Click commands + Rich formatting)
- `interfaces/mcp/` — AI agents (FastMCP tools)
- `interfaces/rest/` — future REST API
- `interfaces/gui/` — future web UI
- `interfaces/sdk/` — future Python SDK

Every interface is a **thin adapter**: parse inputs, call the same controlplane/views/features function, format outputs. If a handler contains business logic, it belongs in `controlplane/` or `views/` instead.

One exception: agent scaffolding (`.desitter/agents.md`, `get_protocol`, `ds init --with-agent`) lives in `interfaces/mcp/` only. It is AI-agent-specific documentation infrastructure, not shared product logic.

---

## 3. The Epistemic Web

### A concrete example first

Consider a physics research project making claims about E8 symmetry theory:

```
Claim C-001: "E8 symmetry predicts the W boson mass"
  └─ depends on Assumption A-001: "The gauge group is compact and simple"
  └─ covered by Analysis AN-001: gauge_couplings.py

Prediction P-001: "W mass = 80.379 GeV"  [Tier A, status: CONFIRMED]
  └─ follows from Claim C-001
  └─ tested by Analysis AN-001
  └─ member of IndependenceGroup G-001: "electroweak_sector"
  └─ observed value: 80.377 GeV
```

The epistemic web is the live, validated graph of all these relationships across an entire research project. The same structure works for machine learning ("Attention is sufficient for sequence modeling" → BLEU score prediction), medicine (drug trial → hazard ratio prediction), or any empirical discipline.

### Entity types

```mermaid
erDiagram
    Claim ||--o{ Assumption : "depends on"
    Claim ||--o{ Claim : "depends_on (DAG)"
    Claim ||--o{ Analysis : "covered_by"
    Prediction }o--o{ Claim : "claim_ids"
    Prediction }o--o{ Assumption : "tests_assumptions"
    Prediction }o--o{ Assumption : "conditional_on"
    Prediction }o--o| Analysis : "analysis"
    Prediction }o--o| IndependenceGroup : "independence_group"
    IndependenceGroup ||--o{ Prediction : "member_predictions"
    IndependenceGroup ||--|| PairwiseSeparation : "separated_from"
    Theory }o--o{ Claim : "related_claims"
    Theory }o--o{ Prediction : "related_predictions"
    DeadEnd }o--o{ Prediction : "related_predictions"
    DeadEnd }o--o{ Claim : "related_claims"
    Analysis ||--o{ Parameter : "uses_parameters"
    Parameter ||--o{ Analysis : "used_in_analyses"
```

| Entity | Role |
|--------|------|
| **Claim** | Atomic falsifiable assertion. Forms a DAG via `depends_on` — derived claims build on foundational ones. `parameter_constraints` is an annotation map `{ParameterId: constraint_str}` — deSitter surfaces these when the referenced parameter changes so the researcher knows to re-check the claim. |
| **Assumption** | Premise taken as given. Empirical [E] assumptions may have a `falsifiable_consequence`; methodological [M] ones describe how the study is run. `depends_on` captures presupposition chains between assumptions. |
| **Prediction** | Testable consequence of one or more claims. Has a tier, status, and measurement regime. `claim_ids` is the full set of claims that jointly imply this prediction. `tests_assumptions` marks assumptions under active test; `conditional_on` marks assumptions taken as given for the prediction to be valid. |
| **Analysis** | A piece of analytical work. deSitter never runs it — the researcher runs it and records the result via `ds record` or the `record_result` MCP tool. `path` and `command` are provenance pointers. `uses_parameters` links to all parameters the analysis depends on, enabling staleness detection. |
| **IndependenceGroup** | A cluster of predictions sharing a common derivation chain. Prevents overcounting correlated evidence — two analyses that both depend on the same data aren't independent. |
| **PairwiseSeparation** | Documents the explicit justification for why two independence groups are genuinely separate. Every pair of groups must have a separation record — enforced by `validate_independence_semantics`. |
| **Theory** | Higher-level explanatory framework. Organises related claims and predictions. |
| **Discovery** | A significant finding worth recording, even if it doesn't fit neatly into claims or predictions. |
| **DeadEnd** | A known dead end or abandoned direction. Valuable negative results that constrain the hypothesis space. |
| **Concept** | A defined vocabulary term specific to the project. |
| **Parameter** | A physical or mathematical constant (e.g., `c = 3e8 m/s`) referenced by analyses. Enables staleness detection: when a parameter changes, `check_stale` identifies which analyses need re-running. `used_in_analyses` is the bidirectional backlink maintained automatically by the web. |

### Bidirectional invariants

Five relationships in the web are **bidirectional** — both sides of the link must always agree. This is enforced at mutation time, not checked after the fact.

| If... | Then... |
|-------|---------|
| `claim.assumptions` contains `A-001` | `assumption.used_in_claims` must contain `C-001` |
| `analysis.claims_covered` contains `C-001` | `claim.analyses` must contain `AN-001` |
| `prediction.independence_group` is `G-001` | `group.member_predictions` must contain `P-001` |
| `prediction.tests_assumptions` contains `A-001` | `assumption.tested_by` must contain `P-001` |
| `analysis.uses_parameters` contains `PAR-001` | `parameter.used_in_analyses` must contain `AN-001` |

**Why bother?** Without this, a claim can reference an assumption that doesn't know it's being used. If you ask "which claims depend on A-001?", the answer is wrong — and you might delete A-001 thinking nothing needs it. Bidirectionality makes graph traversal safe in both directions.

### Domain invariant validators

Ten pure validator functions in `epistemic/invariants.py` check the web on demand. Each takes an `EpistemicWeb` and returns `list[Finding]`. `validate_all` composes them.

| Validator | What it checks |
|-----------|----------------|
| `validate_tier_constraints` | Tier A predictions have 0 free params; Tier B have `conditional_on`; MEASURED predictions have an observed value |
| `validate_independence_semantics` | Group membership consistency; every group pair has a `PairwiseSeparation` |
| `validate_coverage` | Claims without analyses; Tier A predictions without independence groups |
| `validate_assumption_testability` | Empirical assumptions with a `falsifiable_consequence` but no `tested_by` predictions |
| `validate_retracted_claim_citations` | Predictions and claims that still cite retracted claims |
| `validate_implicit_assumption_coverage` | Predictions that implicitly rest on empirical assumptions not in `tests_assumptions` |
| `validate_tests_conditional_overlap` | Predictions where `tests_assumptions` and `conditional_on` share the same assumption (conflicting signals) |
| `validate_foundational_claim_deps` | Foundational claims that incorrectly have `depends_on` entries |
| `validate_evidence_consistency` | CONFIRMED/REFUTED predictions without a linked analysis; analyses with no linked predictions |
| `validate_all` | Composite — runs all validators and returns merged findings |

### Mutation API

`EpistemicWeb` exposes a full copy-on-write mutation API. All methods return a **new web**; the original is untouched.

| Method family | Entities covered |
|---------------|------------------|
| `register_*(entity)` | All 11 entity types: claim, assumption, prediction, analysis, theory, independence_group, discovery, dead_end, concept, parameter, pairwise_separation |
| `update_*(entity)` | claim, assumption, prediction, analysis, theory, independence_group, discovery, dead_end, concept, parameter, pairwise_separation |
| `remove_*(id)` | prediction, claim, assumption, parameter |
| `transition_*(id, new_status)` | prediction, claim, theory, discovery, dead_end |

All `register_*` and `update_*` methods enforce referential integrity (no broken IDs), check for cycles where applicable, and maintain all bidirectional links atomically.

### Traversal and impact queries

The web exposes a set of pure query methods for navigating the graph and computing blast radii. These are the primary tools for AI agents and health-check services.

| Method | Returns | Use case |
|--------|---------|----------|
| `claim_lineage(cid)` | `set[ClaimId]` | All ancestor claims via `depends_on` (transitive closure) |
| `assumption_lineage(cid)` | `set[AssumptionId]` | All assumptions reachable from a claim and its ancestors, including assumption presupposition chains |
| `prediction_implicit_assumptions(pid)` | `set[AssumptionId]` | Every assumption a prediction silently rests on, including `conditional_on` and all assumption `depends_on` chains |
| `refutation_impact(pid)` | `{claim_ids, claim_ancestors, implicit_assumptions}` | What is called into question when a prediction is refuted |
| `assumption_support_status(aid)` | `{direct_claims, dependent_predictions, tested_by}` | Everything that depends on an assumption, directly and transitively |
| `claims_depending_on_claim(cid)` | `set[ClaimId]` | All downstream claims built on this claim (forward traversal) |
| `predictions_depending_on_claim(cid)` | `set[PredictionId]` | All predictions whose derivation chain includes this claim |
| `parameter_impact(pid)` | `{stale_analyses, constrained_claims, affected_claims, affected_predictions}` | Full blast radius of a parameter change |

### Prediction tiers

| Tier | Constraint | What it means |
|------|-----------|---------------|
| **A** | `free_params == 0` | A pure prediction made before seeing the data. No tunable knobs. The gold standard. |
| **B** | must set `conditional_on` | Conditional on auxiliary assumptions beyond the core theory. Still a genuine prediction, but weaker than Tier A. |
| **C** | — | A fit or consistency check. Not a novel prediction — the theory was adjusted to match this data. |

The tier system makes the distinction between "predicted before measurement" and "fit after measurement" explicit and machine-checkable.

### Copy-on-write mutations

Every `EpistemicWeb` mutation returns a **new web**. The original is untouched.

```python
# Before: web has 5 claims
new_web = web.register_claim(claim)  # web is unchanged; new_web has 6 claims

# If validation fails on new_web, we simply discard it.
# web is still intact — free rollback, no cleanup needed.
```

The cost is O(n) memory per mutation (a full deep copy), acceptable at research scale. The benefit: the gateway never needs an explicit undo mechanism.

---

## 4. Data Flow: Registering a Claim

```mermaid
sequenceDiagram
    actor Agent as AI Agent / CLI
    participant GW as Gateway (controlplane/gateway.py)
    participant Repo as JsonRepository
    participant Web as EpistemicWeb
    participant Val as DomainValidator
    participant TxLog as TransactionLog

    Agent->>GW: register("claim", payload)
    GW->>Repo: load()
    Repo-->>GW: web (current state)
    GW->>Web: register_claim(claim)
    Note over Web: checks refs, cycles, updates back-refs
    Web-->>GW: new_web (or raises EpistemicError)
    GW->>Val: validate(new_web)
    Val-->>GW: findings
    alt findings contain CRITICAL
        GW-->>Agent: GatewayResult(status="error", changed=False)
    else clean
        GW->>Repo: save(new_web)
        GW->>TxLog: append("register/claim", claim_id)
        GW-->>Agent: GatewayResult(status="ok", changed=True, tx_id=…)
    end
```

Key properties:

- **Validate-after-write:** the web is mutated in memory first, *then* validated — but *before* writing to disk. If validation finds a CRITICAL issue, the new web is discarded and the original on-disk state is never touched.
- **Single path:** MCP tool handlers and CLI commands call the exact same `Gateway.register()` method. No duplicated logic anywhere.
- **Provenance:** every mutation is logged to the transaction log with a UUID and timestamp, regardless of outcome.

---

## 5. Data Flow: Health Check

```mermaid
sequenceDiagram
    actor Agent as AI Agent / CLI
    participant HC as views/health.py
    participant Val as controlplane/validate.py
    participant Chk as controlplane/check.py

    Agent->>HC: run_health_check(context, repo, validator)
    HC->>Val: validate_structure(web)
    Val-->>HC: structural findings
    HC->>Chk: check_stale(context)
    Chk-->>HC: stale analysis findings
    HC->>Chk: check_refs(context)
    Chk-->>HC: broken reference findings
    HC-->>Agent: HealthReport(overall, findings[])
```

`HealthReport.overall` is `"HEALTHY"`, `"WARNINGS"`, or `"CRITICAL"` — a single machine-readable signal that CI or an agent can act on without parsing the full findings list.

---

## 6. Package Layout and Dependency Rules

```
src/desitter/
├── __init__.py                  # version, public API re-exports
├── __main__.py                  # python -m desitter → CLI
├── config.py                    # DesitterConfig, ProjectContext, ProjectPaths,
│                                #   load_config(), build_context()
│
├── epistemic/                   # ── DOMAIN KERNEL ───────────────────────────
│   ├── types.py                 # NewType IDs, enums, Finding, Severity
│   ├── model.py                 # Entity @dataclasses — no methods, no I/O
│   ├── web.py                   # EpistemicWeb: all mutations to the graph
│   ├── invariants.py            # Pure functions: (EpistemicWeb) -> list[Finding]
│   └── ports.py                 # Abstract interfaces (WebRepository, WebRenderer, …)
│
├── adapters/                    # ── INFRASTRUCTURE ──────────────────────────
│   ├── json_repository.py       # implements WebRepository
│   ├── markdown_renderer.py     # implements WebRenderer
│   └── transaction_log.py       # implements TransactionLog ✔ done
│                                # results_repository.py — Phase 6
│
├── controlplane/                        # ── CORE SERVICES ───────────────────────────
│   ├── gateway.py               # Single mutation/query boundary + GatewayResult
│   ├── validate.py              # validate_project, validate_structure
│   ├── check.py                 # check_stale, check_refs, sync_prose
│   ├── export.py                # export_json, export_markdown
│   └── automation.py            # Render-trigger policy table ✔ done
│                                # results.py — Phase 6
│
├── views/                       # ── VIEW SERVICES ───────────────────────────
│   ├── health.py                # run_health_check → HealthReport
│   ├── render.py                # SHA-256 fingerprint cache + incremental render
│   ├── status.py                # get_status → ProjectStatus
│   └── metrics.py               # compute_metrics, tier_a_evidence_summary
│
└── interfaces/                  # ── INTERFACE ADAPTERS ──────────────────────
    ├── __init__.py              # Interface layer contract documentation
    ├── cli/                     # Humans + scripts
    │   ├── main.py              # Click command tree
    │   └── formatters.py        # Rich tables + JSON fallback
    └── mcp/                     # AI agents
        ├── server.py            # FastMCP entry point
        └── tools.py             # Tool handlers → thin wrappers over controlplane/views
        # future: rest/, gui/, sdk/ go here as equal peers
```

### Allowed import directions

| From | May import | May NOT import |
|------|-----------|----------------|
| `epistemic/` | stdlib only | anything |
| `adapters/` | `epistemic/`, stdlib | `controlplane/`, `views/`, `interfaces/` |
| `config.py` | stdlib only | anything |
| `controlplane/` | `epistemic/`, `adapters/` (via protocols), `config` | `views/`, `interfaces/` |
| `views/` | `controlplane/`, `epistemic/`, `config` | `interfaces/` |
| `interfaces/*` | all layers above | other interfaces (e.g. `cli/` cannot import `mcp/`) |

`controlplane/` accesses adapters **only through the abstract interfaces defined in `epistemic/ports.py`** — it never imports a concrete adapter class directly. Concrete adapters are wired in the interface layer at startup when the Gateway is constructed.

---

## 7. The Gateway

The Gateway is the **single mutation and query boundary**. Both MCP tool handlers and CLI commands call it. There is no other way to mutate the epistemic web.

```python
class Gateway:
    def register(self, resource: str, payload: dict, *, dry_run: bool) -> GatewayResult
    def get(self, resource: str, identifier: str) -> GatewayResult
    def list(self, resource: str, **filters) -> GatewayResult
    def set(self, resource: str, identifier: str, payload: dict, *, dry_run: bool) -> GatewayResult
    def transition(self, resource: str, identifier: str, new_status: str, *, dry_run: bool) -> GatewayResult
    def query(self, query_type: str, **params) -> GatewayResult
```

All operations return a `GatewayResult`:

```python
@dataclass
class GatewayResult:
    status: str           # "ok" | "error" | "CLEAN" | "BLOCKED" | "dry_run"
    changed: bool         # True if on-disk state was modified
    message: str          # human-readable summary
    findings: list[Finding]
    transaction_id: str | None  # set on successful mutations; None for reads
    data: dict | None           # populated for get/list/query results
```

This envelope is the contract between the Gateway and all interfaces. MCP tools serialize it to a dict. The CLI formatter renders it with Rich. A future REST API would serialize it to JSON. The contract never changes shape — only how it is presented changes.

`dry_run=True` runs the full mutation and validation pipeline in memory but skips `repo.save()` — useful for checking whether a change would be accepted before committing it.

### Resource aliases

The gateway accepts flexible resource names and resolves them to canonical keys:

```python
GATEWAY_RESOURCE_ALIASES = {
    "claim": "claim", "claims": "claim",
    "prediction": "prediction", "predictions": "prediction",
    "analysis": "analysis", "analyses": "analysis",
    "independence-group": "independence_group",
    # ...
}
```

Adding a new resource type means one entry in this table.

### Transaction lifecycle

```
1. resolve_resource(alias)       → canonical key (raises KeyError if unknown)
2. repo.load()                   → current EpistemicWeb from disk
3. web.register_*(entity)        → new EpistemicWeb in memory
                                   raises EpistemicError on broken refs, cycles, duplicates
4. validator.validate(new_web)   → list[Finding]
5. if any CRITICAL findings      → discard new_web, return GatewayResult(status="error")
                                   on-disk state is untouched
6. repo.save(new_web)            → write to disk (atomic rename)
7. tx_log.append(op, id)         → append provenance record, get transaction_id
8. return GatewayResult(status="ok", changed=True, tx_id=…)
```

---

## 8. ProjectContext

`ProjectContext` is the runtime configuration object passed to every service. It carries data, not callbacks — no hidden collaborators, no module-level globals.

```python
@dataclass
class ProjectContext:
    workspace: Path
    config: DesitterConfig    # project_dir, …
    paths: ProjectPaths      # all derived filesystem paths, computed once at startup
```

`ProjectPaths` is computed once in `build_context()` and never re-derived. Every service that needs a file path reads it from `context.paths`. This makes all services fully testable: pass in a `ProjectContext` pointing at a temp directory and nothing touches the real filesystem.

```mermaid
graph LR
    workspace["workspace/"] --> |"build_context()"| ctx["ProjectContext"]
    ctx --> GW["controlplane/gateway.py"]
    ctx --> HC["views/health.py"]
    ctx --> ST["views/status.py"]
    ctx --> CH["controlplane/check.py"]
```

---

## 9. The Adapter Pattern

### The problem it solves

The domain core (`epistemic/`) needs to load and save the web, render views, and record results — but it shouldn't know whether storage is JSON files, a database, or an in-memory dict. Hardcoding `JsonRepository` into the domain would mean tests need real JSON files and swapping storage formats would require changing domain code.

### How it works

`epistemic/ports.py` defines **what the domain needs** from infrastructure using Python `Protocol` classes — structural interfaces: any class with the right methods satisfies the protocol without needing to inherit from it.

```python
# epistemic/ports.py — the interface (what the domain requires)
class WebRepository(Protocol):
    def load(self) -> EpistemicWeb: ...
    def save(self, web: EpistemicWeb) -> None: ...

# adapters/json_repository.py — production implementation
class JsonRepository:
    def load(self) -> EpistemicWeb: ...   # reads project/data/*.json
    def save(self, web: EpistemicWeb) -> None: ...

# In tests: a fake that needs no files at all
class InMemoryRepository:
    def __init__(self, web: EpistemicWeb): self._web = web
    def load(self) -> EpistemicWeb: return self._web
    def save(self, web: EpistemicWeb) -> None: self._web = web
```

The `Gateway` receives a `WebRepository` — it never imports `JsonRepository` directly. The concrete adapter is injected at startup in `interfaces/mcp/tools.py` and `interfaces/cli/main.py`. This is sometimes called "ports and adapters" (Hexagonal Architecture) or dependency injection.

```mermaid
graph LR
    GW["Gateway"] -->|"calls load() / save()"| PORT["WebRepository (Protocol)"]
    PORT -.->|"implemented by"| JSON["JsonRepository"]
    PORT -.->|"implemented by"| MEM["InMemoryRepository (tests)"]
```

---

## 10. Key Design Decisions

### The Audit Scaffold Principle

deSitter surfaces structural facts; it never makes logical judgments. This shapes every API:

- `get_structural_gaps` returns observations, not recommendations
- `health_check` reports invariant violations, not research strategy
- `check_stale` identifies which analyses need re-running after a parameter change — it does not decide whether re-running is necessary

This keeps deSitter domain-neutral and usable across disciplines. A system that understood "what to do next" would need to understand the research domain. A system that surfaces "what is structurally incomplete" works for physics, medicine, and ML equally.

### Consumer model (no execution)

deSitter does not run analyses. The researcher runs them using their preferred tools (SageMath, Python, R, Jupyter) and records results via `ds record` or the `record_result` MCP tool.

Analysis entities carry `path` and `command` as documentation only — provenance pointers the researcher can follow. The git SHA at record time is captured on the result, giving an immutable chain: `path + SHA + recorded value`.

This is a deliberate constraint: no sandbox, no subprocess, no supply-chain risk from executing researcher code.

### Immutable mutations (copy-on-write)

Every `EpistemicWeb` mutation returns a new web. This is O(n) per mutation (a full deep copy) but correct and simple. For research-scale webs (hundreds to low thousands of entities) this is fast enough. The benefit: free rollback — the gateway discards the new web if validation fails, with no undo stack needed.

### Native Python types

Entities use `dict`, `set`, `list` — not `frozenset`, `Mapping`, or `tuple`. The `EpistemicWeb` and the gateway are the encapsulation boundaries, not the container types. This keeps entity construction simple and test fixtures readable: you can construct any entity with plain Python literals.

### Structural vs. semantic invariants

Two categories of constraint, enforced at different times:

- **Structural invariants** (referential integrity, DAG acyclicity, bidirectional links) are enforced *inside* `EpistemicWeb.register_*` at mutation time. They are guaranteed by construction.
- **Semantic invariants** (tier constraints, coverage gaps, testability) live in `invariants.py` and are checked on demand by the validator. They represent best-practice rules that may legitimately be incomplete during active research.

### One gateway, many interfaces

All interfaces are presentations, not implementations. All business logic lives in the gateway and the service layers. This means:

- A bug fixed in the gateway is fixed for CLI, MCP, and any future interface simultaneously
- Adding a new resource type requires no changes to any interface's dispatch logic
- Testing the gateway fully tests the product behaviour
- Adding a REST API or GUI means writing one new `interfaces/` directory, nothing else

### Dependency inversion at every boundary

```
interfaces/*  →  features  →  views  →  core  →  epistemic  ←  adapters
```

`epistemic/` defines the interfaces. `adapters/` implements them. `controlplane/` uses them. The domain has zero knowledge of JSON files, markdown, or the MCP protocol. The entire epistemic kernel and core services can be tested in memory without touching the filesystem.

---

## 11. Architecture Remediation Plan

This roadmap fixes cross-layer architecture issues first, then fills in planned stubs in phase order.

### Implementation policy for planned stubs

Intentionally unimplemented modules must not be filled ad hoc during architecture cleanup. They are tracked in `TRACKER.md` and implemented only in their owning phase.

### Top 5 issues and PR-sized milestones

| Priority | Issue | Target outcome | PR-sized milestones |
|----------|-------|----------------|---------------------|
| P0 | Boundary contract mismatches between interfaces and services | No runtime signature mismatch at MCP/CLI boundaries | PR-A1: remove private collaborator reach-through from interface code; PR-A2: align MCP calls with service signatures (`render_all`, `check_refs`); PR-A3: add boundary contract tests to prevent regressions |
| P0 | Gateway orchestration is still stubbed | All register/get/list/set/transition/query routes execute through one mutation boundary | PR-B1: implement load-mutate-validate-save transaction flow for `register`; PR-B2: implement read/query routes (`get`, `list`, `query`); PR-B3: implement `set`/`transition` with dry-run and transaction logging |
| P1 | Adapter layer incomplete (`JsonRepository`, `MarkdownRenderer`) | End-to-end persistence and rendering works through ports | PR-C1: implement typed load/save round-trip for all entities; PR-C2: implement markdown surface rendering; PR-C3: add adapter round-trip and rendering contract tests |
| P1 | View/controlplane read services incomplete (`validate`, `check`, `render`, `status`, `metrics`, `health`, `export`) | Health, status, validation, stale checks, export, and render paths are callable from both interfaces | PR-D1: implement `validate_project` and `check_refs`; PR-D2: implement `metrics` and `status`; PR-D3: implement `render` cache flow plus `health` aggregation and export |
| P2 | Interface parity and output-contract hardening | CLI and MCP expose the same behavior and stable envelopes | PR-E1: implement CLI command delegation with no business logic in handlers; PR-E2: normalize JSON envelope schemas across MCP/CLI; PR-E3: add parity tests asserting same semantics from both adapters |

---

## 12. Boundary Test Matrix

This matrix closes current blind spots quickly while stubs remain tracked.

| Boundary | Test type | What to assert | Fixture strategy | Priority |
|----------|-----------|----------------|------------------|----------|
| CLI -> Gateway | Adapter delegation tests | CLI parses payload/options and calls exactly one gateway operation; no business branching in CLI | `click.testing.CliRunner` + fake gateway object | P0 |
| MCP -> Gateway | Tool wrapper contract tests | Tool handlers forward args correctly and return status-first envelope shape | Fake server decorator + fake gateway, no FastMCP runtime needed | P0 |
| MCP -> Views/Check/Validate | Signature and envelope tests | `render_views`, `check_refs`, `health_check`, `project_status` call service functions with correct args and return machine-stable fields | Monkeypatched service functions returning deterministic fixtures | P0 |
| Gateway -> Repository/Validator/TxLog | Transaction orchestration tests | validate-after-write flow, rollback on CRITICAL, dry-run no-save, tx log append on writes | In-memory repo + fake validator + fake tx log | P0 |
| Views (`health`, `status`, `metrics`) | Read-model tests | Aggregation logic and severity rollups are deterministic | Small canonical web fixtures with focused findings | P1 |
| Render cache (`views/render`) | Cache behavior tests | unchanged fingerprint skips writes; changed fingerprint writes and updates cache | temp directory cache file + fake renderer output | P1 |
| Check services (`check_stale`, `check_refs`) | Consistency tests | stale/ref findings match known graph states | synthetic mini-web builders | P1 |
| Interface parity (CLI vs MCP) | Black-box parity tests | same operation yields same status semantics and equivalent data payloads | shared fixture payloads and normalization helper | P2 |

Suggested execution order:
1. P0 tests first, because they catch architecture boundary drift immediately.
2. P1 tests next, because they stabilize read services before feature expansion.
3. P2 parity tests after both adapters are mostly implemented.

---

## 13. Scale Strategy For Query Performance

The current graph query methods are correct for research-scale webs but include repeated traversals and repeated index construction. If large graph workloads matter now, add query indexes behind the same public methods.

### Current hotspots

| Method | Current behavior | Typical cost |
|--------|------------------|--------------|
| `assumption_support_status` | Rebuilds implicit assumption -> prediction dependents by scanning all predictions | O(P * I) per call, where `I` is average implicit assumption count |
| `parameter_impact` | Repeatedly recomputes claim downstream and prediction impact per affected claim | O(C + A + P + traversal overhead) with repeated set merges |
| `validate_implicit_assumption_coverage` | Recomputes implicit assumption sets across all predictions | O(P * I) per validation pass |

### Proposed index set

| Index | Key -> Value | Used by | Build strategy |
|-------|--------------|---------|----------------|
| `implicit_assumption_to_predictions` | `AssumptionId -> set[PredictionId]` | `assumption_support_status`, `validate_implicit_assumption_coverage` | Lazy build on first query; invalidate on prediction/claim/assumption mutation |
| `claim_to_downstream_claims` | `ClaimId -> set[ClaimId]` | `predictions_depending_on_claim`, `parameter_impact` | Precompute reverse graph closure once per web version |
| `analysis_to_predictions` | `AnalysisId -> set[PredictionId]` | `parameter_impact` | Build from prediction registry |
| `parameter_to_constrained_claims` | `ParameterId -> set[ClaimId]` | `parameter_impact` | Build from claim `parameter_constraints` |

### Complexity improvements (expected)

| Query | Before | After |
|-------|--------|-------|
| `assumption_support_status` | O(P * I) | O(1) lookup + output size |
| `validate_implicit_assumption_coverage` | O(P * I) per pass | O(total indexed edges) reuse with minimal extra filtering |
| `parameter_impact` | repeated downstream traversal per affected claim | O(index lookups + union cost), no repeated graph walks |

### Rollout plan

1. Add an internal immutable query-index container attached to `EpistemicWeb`.
2. Build indexes lazily per web instance and cache them for repeated queries.
3. Keep public method signatures unchanged to preserve interface compatibility.
4. Add benchmark tests for small, medium, and large synthetic graphs.
5. Guard rollout with feature flag until benchmark thresholds are met.
