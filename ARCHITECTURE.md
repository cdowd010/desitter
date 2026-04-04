# Architecture

This document explains how deSitter works from the ground up. It starts with the innermost kernel — the pure Python domain that defines what research knowledge *is* and how it holds together — and builds outward through each layer in turn, finishing at the human and AI interfaces where researchers and agents actually interact with the system. Readers who want to understand why the system is structured the way it is, how the pieces fit together, or where to add new behaviour should read this end-to-end. Readers who want to understand only one specific layer can jump directly to that section, but the kernel section is a prerequisite for all of them.

---

## Project Layout

The entire Python package lives under `src/desitter/`. The directory structure reflects the layered architecture directly — each sub-package corresponds to one architectural ring:

```
src/desitter/
├── __init__.py                    # Package entry point
├── __main__.py                    # python -m desitter entry point
├── config.py                      # Configuration loading and path derivation
│
├── epistemic/                     # The kernel — pure domain, no I/O
│   ├── types.py                   # Typed IDs, enums, Finding dataclass
│   ├── model.py                   # Entity dataclasses (Claim, Prediction, etc.)
│   ├── web.py                     # EpistemicWeb aggregate root
│   ├── invariants.py              # Domain validation rules (pure functions)
│   └── ports.py                   # Abstract protocols for external services
│
├── adapters/                      # Implementations of the kernel's ports
│   ├── json_repository.py         # JSON-file persistence for EpistemicWeb
│   ├── markdown_renderer.py       # Markdown view generation
│   └── transaction_log.py         # Append-only JSONL provenance log
│
├── controlplane/                  # Orchestration: load → mutate → validate → save
│   ├── gateway.py                 # Single mutation/query boundary
│   ├── factory.py                 # Composition root — wires concrete adapters
│   ├── automation.py              # Declarative render-trigger policy table
│   ├── check.py                   # Staleness and reference integrity checks
│   ├── validate.py                # Validation orchestration helpers
│   └── export.py                  # Bulk export (JSON / Markdown snapshots)
│
├── views/                         # Read-only aggregation and rendering
│   ├── status.py                  # Project status snapshots
│   ├── health.py                  # Composed health reports
│   ├── metrics.py                 # Quantitative web statistics
│   └── render.py                  # Incremental markdown rendering with SHA cache
│
└── interfaces/                    # Outermost ring — human and agent surfaces
    ├── cli/
    │   ├── main.py                # Click command tree
    │   └── formatters.py          # Rich terminal and JSON output
    └── mcp/
        ├── server.py              # FastMCP server construction and startup
        └── tools.py               # MCP tool handlers (thin wrappers over gateway)
```

The on-disk project data that deSitter manages lives outside the package, in a directory the researcher specifies (default: `project/` in the workspace root):

```
workspace/
└── project/                       # configurable via desitter.toml
    ├── data/                      # one JSON file per entity type
    │   ├── claims.json
    │   ├── assumptions.json
    │   ├── predictions.json
    │   ├── analyses.json
    │   ├── theories.json
    │   ├── independence_groups.json
    │   ├── pairwise_separations.json
    │   ├── discoveries.json
    │   ├── dead_ends.json
    │   └── parameters.json
    ├── views/                     # rendered markdown surfaces
    └── .cache/
        ├── render.json            # SHA-256 render fingerprint cache
        └── transaction_log.jsonl  # append-only mutation provenance log
```

---

## The Problem This System Solves

Research projects accumulate a hidden graph of dependencies between ideas. A claim depends on an assumption. A prediction follows from that claim. An analysis tests that prediction. A parameter change invalidates the analysis. These relationships exist whether or not you track them, but when they are implicit, they break silently: a refuted prediction does not update the claims that rely on it, a changed assumption does not propagate, a deleted entity leaves broken references in a dozen other records, and months later nobody knows why a conclusion was drawn or whether the underlying support was ever intact.

**Epistemic** means "relating to knowledge and how it is justified." An **epistemic web** is the explicit, machine-checkable graph of those dependencies — what claims exist, what they depend on, what predictions they make, what evidence supports or refutes them, and which analyses performed by the researcher tested which predictions. deSitter manages, validates, and exposes that graph.

deSitter is an **audit scaffold**, not a reasoning engine. It surfaces structural facts about the epistemic graph — missing links, untested assumptions, uncovered predictions, parameter-staleness chains — and gives researchers and AI agents the navigational structure to do their own reasoning. It never makes logical judgments about whether a theory is correct. It never prescribes which experiment to run next. A system that understood what to do next would need to understand the research domain. A system that surfaces what is structurally incomplete works equally well for physics, medicine, machine learning, or any empirical discipline.

---

## The Epistemic Kernel

The kernel is the innermost ring of the system. It lives entirely in `src/desitter/epistemic/` and consists of five Python modules: `types.py`, `model.py`, `web.py`, `invariants.py`, and `ports.py`. The kernel has a single hard rule: **it performs no I/O and imports nothing outside the Python standard library.** No JSON parsing, no file writes, no database calls, no HTTP, no subprocesses. This constraint is what makes the kernel testable in isolation and what lets every layer above it depend on the kernel without pulling in any infrastructure concerns.

### How the Five Kernel Modules Relate

Before reading each module in detail, it helps to see how they fit together:

```
types.py          — vocabulary: enums, typed IDs, the Finding dataclass
    ↓ used by
model.py          — entities: ten dataclasses built from those types
    ↓ used by
web.py            — aggregate root: owns all ten entity dicts, enforces all
                    structural invariants, exposes mutation and query methods
    ↓ validated by
invariants.py     — semantic rules: ten pure validator functions that take a
                    complete EpistemicWeb and return list[Finding]
    ↓ shapes described by
ports.py          — abstract protocols: the interfaces the kernel requires
                    from the outside world (repository, renderer, etc.)
```

`types.py` and `model.py` are pure data. `web.py` is the only place where the data is assembled into a coherent whole and structural rules are enforced. `invariants.py` adds semantic rules on top of the structural ones. `ports.py` describes what external services the kernel needs without naming any concrete implementation.

### Foundation: Typed Identifiers and Value Types (`types.py`)

Before any entity can be defined, the kernel needs a vocabulary of types. Every entity in the system has a string identifier, but allowing a `ClaimId` to be passed where a `PredictionId` is expected would be a silent bug — a prediction that claims to depend on "P-001" but actually meant "C-001" is a data corruption issue, not a type error, if all IDs are plain strings.

The kernel uses Python's `NewType` to give each identifier a distinct static type:

```python
ClaimId                = NewType("ClaimId", str)
AssumptionId           = NewType("AssumptionId", str)
PredictionId           = NewType("PredictionId", str)
AnalysisId             = NewType("AnalysisId", str)
ParameterId            = NewType("ParameterId", str)
TheoryId               = NewType("TheoryId", str)
DiscoveryId            = NewType("DiscoveryId", str)
DeadEndId              = NewType("DeadEndId", str)
IndependenceGroupId    = NewType("IndependenceGroupId", str)
PairwiseSeparationId   = NewType("PairwiseSeparationId", str)
```

At runtime, a `ClaimId` is just a string. The `NewType` is zero-cost. But the static type checker treats `ClaimId` and `PredictionId` as incompatible types, so passing one where the other is expected is caught before the code runs. This is not a runtime guard — it is documentation that the type checker can enforce.

The module also defines several enums that classify entity state. The most important ones for understanding system behaviour:

**`ConfidenceTier`** classifies how strongly constrained a prediction is.
- `FULLY_SPECIFIED`: the prediction was made with zero free parameters — a pure forecast from theory before any data was seen. This is the gold standard. The system enforces that `free_params == 0` for any prediction in this tier.
- `CONDITIONAL`: the prediction is valid only if explicitly stated auxiliary assumptions hold. These are real predictions, but weaker than `FULLY_SPECIFIED` because they depend on more than the core theory.
- `FIT_CHECK`: the theory was fit to the data, or the data predates the model. Agreement here is unsurprising and constitutes weak evidence at best. The tier makes this explicit.

**`EvidenceKind`** classifies how a prediction relates temporally and methodologically to data.
- `NOVEL_PREDICTION`: the forecast was generated before relevant measurements existed.
- `RETRODICTION`: the prediction explains already-observed data that was not used to fit parameters.
- `FIT_CONSISTENCY`: the agreement is with data that was part of the original fitting procedure.

**`MeasurementRegime`** classifies what kind of observational data backs a prediction.
- `MEASURED`: a direct measurement exists.
- `BOUND_ONLY`: only an upper or lower bound has been established — no precise measurement.
- `UNMEASURED`: no observational data exists yet.

**`PredictionStatus`** tracks the lifecycle of a prediction as evidence accumulates:
`PENDING → CONFIRMED | STRESSED | REFUTED | NOT_YET_TESTABLE`.
The `STRESSED` state is meaningful: it means current evidence introduces tension but does not decisively refute the prediction. It is a signal for human review, not an automated conclusion.

**`Severity`** applies to `Finding` objects produced by validators:
- `CRITICAL` means a blocking integrity violation that the gateway will refuse to write.
- `WARNING` means a potential issue worth reviewing but not blocking.
- `INFO` is non-blocking context.

A `Finding` is simply:

```python
@dataclass
class Finding:
    severity: Severity
    source:   str      # e.g. "predictions/P-001", "independence_groups/G-002"
    message:  str      # human-readable description of the issue
```

Findings are the system's output language. Every validator, health check, and structural inspection returns a list of `Finding` objects. The location-tagged `source` field lets an interface renderer hyperlink directly to the problematic entity.

### The Entity Model (`model.py`)

`model.py` contains ten dataclasses — one per entity type in the epistemic web. Each is a pure data record: no methods, no I/O, no logic. Relationships between entities are expressed as sets of typed identifiers, not as object references. To navigate from a `Prediction` to its supporting `Claim` objects, you hold the prediction's `.claim_ids` (a `set[ClaimId]`) and ask the `EpistemicWeb` to look them up. This keeps entities lightweight and makes the `EpistemicWeb` the single place where referential integrity is enforced.

#### Entity Identity: How IDs Are Assigned

Every entity requires an ID field (e.g. `ClaimId`, `PredictionId`) provided by the **caller** at registration time. The system never auto-generates IDs. The conventional format — `C-001`, `P-001`, `AN-001`, `PAR-001`, `IG-001` — is a project convention, not an enforced rule. Any string is accepted as an ID.

| Entity type          | Conventional prefix | Example          |
|----------------------|---------------------|------------------|
| `Claim`              | `C-`                | `C-001`          |
| `Assumption`         | `A-`                | `A-001`          |
| `Prediction`         | `P-`                | `P-001`          |
| `Analysis`           | `AN-`               | `AN-001`         |
| `Parameter`          | `PAR-`              | `PAR-001`        |
| `Theory`             | `T-`                | `T-001`          |
| `Discovery`          | `D-`                | `D-001`          |
| `DeadEnd`            | `DE-`               | `DE-001`         |
| `IndependenceGroup`  | `IG-`               | `IG-001`         |
| `PairwiseSeparation` | `PS-`               | `PS-001`         |

What the system *does* enforce:
- **No duplicates**: `register_*` raises `DuplicateIdError` if the ID already exists in the web.
- **Referential integrity**: `register_*` and `update_*` raise `BrokenReferenceError` if any referenced ID does not exist in the web.
- **Type safety at check time**: the type checker rejects passing a `ClaimId` where a `PredictionId` is expected, even though both are strings at runtime.

What the system does *not* enforce:
- Format (e.g. that a `ClaimId` starts with `"C-"`).
- Sequential numbering.

Choosing IDs is the researcher's responsibility. Pick them to be stable and human-readable; they appear in every cross-reference and in the transaction log.

#### The Entities

**`Claim`** is an atomic, falsifiable assertion. The most fundamental unit. Claims form a directed acyclic graph through their `depends_on` set: a derived claim lists the claims it is built on, and the web ensures no cycles exist. `assumptions` links to the premises a claim takes as given; `analyses` links to the analyses that cover it. Both of these are bidirectional — adding a claim to `analyses` automatically adds the corresponding entry on the `Analysis` side, and the web enforces that both sides always agree. The `parameter_constraints` field is an annotation map `{ParameterId: constraint_str}` — a human-readable threshold like `"< 0.05"` or `"> 3.0"`. deSitter does not evaluate these constraints. It surfaces them when the referenced parameter changes, so the researcher knows which claims have thresholds that might now need revisiting.

**`Assumption`** is a premise taken as given. Empirical assumptions (`AssumptionType.EMPIRICAL`) should have a `falsifiable_consequence` — a description of what would need to be observed to falsify the assumption — and `tested_by` links to predictions explicitly designed to test whether the assumption holds. Methodological assumptions describe how the study is conducted and may not have falsifiable consequences. Assumptions themselves can depend on other assumptions through `depends_on`, capturing presupposition chains: "the detector is linear" presupposes "the detector is calibrated." The `assumption_lineage` traversal in the web follows both claim-to-assumption and assumption-to-assumption chains so that no silent dependency is missed.

**`Prediction`** is a testable consequence jointly implied by one or more claims. Several of its fields require careful explanation because they address subtly different questions:

- `claim_ids`: the claims that *together* imply this prediction. Most non-trivial predictions require multiple claims simultaneously; this field captures the complete derivation set.
- `tests_assumptions`: assumptions this prediction was explicitly designed to test. Its outcome bears on whether those assumptions hold. When a `REFUTED` prediction names an assumption here, the researcher knows that assumption is under pressure. Bidirectional with `Assumption.tested_by`.
- `conditional_on`: assumptions the prediction is *conditioned on* — taken as given rather than under active test. The prediction is only expected to hold if these assumptions hold. Unlike `tests_assumptions`, these are backstops rather than targets. The `CONDITIONAL` tier requires this field to be populated.
- `independence_group`: the `IndependenceGroupId` of the group this prediction belongs to. Used to prevent overcounting correlated evidence.
- `derivation`: prose explanation of *why* `claim_ids` jointly imply this prediction. The logical argument.
- `specification`: the formula or relationship being tested. The *what*, distinct from the *why*.
- `evidence_kind`: the `EvidenceKind` enum value classifying the temporal relationship between the prediction and data.
- `free_params`: the number of tunable degrees of freedom in the prediction. Must be zero for `FULLY_SPECIFIED` predictions.
- `falsifier`: the criterion that would count as refutation.

**`Analysis`** represents a piece of work the researcher has run (or will run) using their own tools. deSitter never executes it. The `path` and `command` fields are provenance documentation only — a record of where the code lives and how to invoke it. The `uses_parameters` field links to every `Parameter` the analysis depends on. When any of those parameters change, the health check surfaces this analysis as stale and flags all predictions linked to it. Bidirectional with `Parameter.used_in_analyses`.

Recording an analysis result — capturing the output and the git SHA of the code at the time it ran — will be done via `ds record` (CLI) or `record_result` (MCP tool). These operations are planned and documented in the entity design but not yet implemented; see the [Implementation Status](#implementation-status) section.

**`IndependenceGroup`** exists because of a subtle statistical requirement: if two predictions both follow from the same data source, they are not independent evidence for the shared claim. Overcounting correlated confirmations inflates the apparent evidentiary support. An `IndependenceGroup` clusters predictions that share a common derivation chain. Every pair of groups must then supply explicit justification for why they are genuinely independent — recorded as a `PairwiseSeparation`. This makes the independence structure of evidence visible and machine-checkable.

**`PairwiseSeparation`** records the justification for why two `IndependenceGroup` entities are genuinely separate. Its `basis` field is human-readable prose. The validator enforces that every pair of groups has a separation record, so the independence structure can never be partially specified.

**`Theory`** is a higher-level explanatory framework. It organises related claims and predictions but does not add structural dependencies the web enforces — it is a navigational organiser. A `Theory` has a status lifecycle (`ACTIVE`, `DEPRECATED`, `REFUTED`, `SPECULATIVE`) that can be advanced through `transition_theory`.

**`Discovery`** records a significant finding during research, even when it does not fit neatly into claims or predictions. Research produces surprises; this entity captures them with a date, impact description, and optional links to related claims or predictions.

**`DeadEnd`** records a known abandoned direction with a description of what was tried and why it failed. Negative results constrain the hypothesis space and should not be silently discarded because the current code cannot find a reference to them.

**`Parameter`** is a physical or mathematical constant referenced by analyses: masses, coupling constants, significance thresholds, model hyperparameters. Parameters live in a version-controlled JSON file rather than inside analysis scripts so that a single authoritative value is shared across all analyses and changes are tracked with full provenance. The `used_in_analyses` field (bidirectional with `Analysis.uses_parameters`) enables the staleness detection cascade: change a parameter, the health check tells you exactly which analyses need re-running and which predictions are therefore stale.

### The Aggregate Root: `EpistemicWeb` (`web.py`)

`EpistemicWeb` is the most important class in the system. It is the **aggregate root** of the epistemic domain — the single object that owns the complete research state and is the only legitimate path through which any mutation to that state can occur. Nothing outside the web ever modifies an entity directly. Everything goes through the web's methods, because the web is responsible for maintaining every invariant.

The class itself is a dataclass holding ten dictionaries, one per entity type, all keyed by typed identifiers:

```python
@dataclass
class EpistemicWeb:
    claims:               dict[ClaimId, Claim]
    assumptions:          dict[AssumptionId, Assumption]
    predictions:          dict[PredictionId, Prediction]
    analyses:             dict[AnalysisId, Analysis]
    theories:             dict[TheoryId, Theory]
    independence_groups:  dict[IndependenceGroupId, IndependenceGroup]
    pairwise_separations: dict[PairwiseSeparationId, PairwiseSeparation]
    discoveries:          dict[DiscoveryId, Discovery]
    dead_ends:            dict[DeadEndId, DeadEnd]
    parameters:           dict[ParameterId, Parameter]
```

These dictionaries are not exposed directly for modification. The entire public surface for mutation is a family of methods that return a **new `EpistemicWeb`** rather than modifying the existing one.

#### Copy-on-Write Mutation Semantics

Every mutation method follows the same pattern:

1. Deep-copy the current web into a new instance via `_copy()`.
2. Validate that all referenced IDs exist in the new instance.
3. Perform the structural check (no cycles, no duplicates).
4. Write the new entity into the new instance's dictionary.
5. Update all bidirectional backlinks in the new instance.
6. Return the new instance.

The original web is never touched.

```python
# This is safe:
original_web = ...                                # has 5 claims
new_web = original_web.register_claim(new_claim)  # original_web still has 5

# If the caller discovers the new web is wrong, it simply discards it.
# The original_web is still intact. No undo stack needed.
```

The cost of this approach is O(n) memory per mutation — a full deep copy of all ten dictionaries via Python's `copy.deepcopy`. For research-scale webs (hundreds to low thousands of entities) this is fast enough, measured in microseconds. The benefit is correctness without complexity: failure at any subsequent validation step means the caller throws away the new web and the disk state is never affected. There is no concept of a "partially committed" mutation.

#### Mutation Method Families

The web exposes three families of mutation methods, one per operation class:

- **`register_*(entity)`** — adds a new entity. Raises `DuplicateIdError` if the ID already exists. After checking for duplicates and referential integrity, calls the internal `_copy()` method, writes the entity into the copy, wires all bidirectional backlinks, and returns the copy.
- **`update_*(entity)`** — replaces an existing entity with a new version. Raises `BrokenReferenceError` if the entity does not exist. Rewires all bidirectional backlinks that may have changed. Returns a new web with the entity replaced.
- **`transition_*(id, new_status)`** — advances the status lifecycle of an entity (e.g. `PENDING → CONFIRMED`). Returns a new web with only the status field changed. Status transitions are the only mutations that do not require revalidating referential integrity (the entity already exists; no new references are added).
- **`remove_*(id)`** — removes an entity. Scrubs all occurrences of the removed ID from every other entity's reference sets before returning the new web, so no dangling references survive.

#### Referential Integrity Enforcement

Every `register_*` and `update_*` method checks that all IDs referenced by the new entity actually exist in the web before the entity is written. If a `Prediction` names a `ClaimId` in `claim_ids` and no such claim exists, the method raises `BrokenReferenceError` immediately. This makes referential integrity a property guaranteed by construction, not a property verified after the fact.

#### Cycle Detection

The `depends_on` fields on both `Claim` and `Assumption` form directed graphs. The web enforces that these are acyclic: if registering a new claim would create a cycle in the `depends_on` graph, the method raises an `EpistemicError`. The algorithm is a simple DFS from the new node's `depends_on` set, checking whether any transitive predecessor equals the new node's own ID.

#### Bidirectional Invariants

Five relationships in the web are **bidirectional**: both sides of the link must always agree. The web maintains these atomically at mutation time. There is no separate "sync" step.

| Forward link | Reverse link | Maintained by |
|---|---|---|
| `Claim.assumptions` contains `A-001` | `Assumption.used_in_claims` contains `C-001` | `register_claim`, `update_claim` |
| `Analysis.claims_covered` contains `C-001` | `Claim.analyses` contains `AN-001` | `register_analysis`, `update_analysis` |
| `Prediction.independence_group` is `G-001` | `IndependenceGroup.member_predictions` contains `P-001` | `register_prediction`, `update_prediction` |
| `Prediction.tests_assumptions` contains `A-001` | `Assumption.tested_by` contains `P-001` | `register_prediction`, `update_prediction` |
| `Analysis.uses_parameters` contains `PAR-001` | `Parameter.used_in_analyses` contains `AN-001` | `register_analysis`, `update_analysis` |

Why does this matter? Without bidirectional maintenance, the answer to "which claims depend on assumption A-001?" is derived by scanning all claims. That is slow, but more critically, it is fragile: if the `used_in_claims` backlink is wrong (perhaps because a past mutation forgot to update it), the answer silently returns the wrong set. Someone might then safely delete A-001, thinking nothing depends on it, when in fact several claims do. Bidirectionality makes graph traversal safe in both directions and prevents a whole class of silent corruption bugs.

When a mutation removes an entity — say, `remove_claim(cid)` — the web scrubs all occurrences of that ID from every other entity's reference sets before writing the new state. The result is that no entity in the returned web contains a reference to a non-existent ID.

#### Graph Traversal Methods

The web provides a set of pure query methods that compute structural properties of the graph. These are used by validators, health checks, and AI agents to navigate the epistemic structure. None of them modify the web.

**`claim_lineage(cid)`** computes the transitive closure of `depends_on` starting from a given claim, walking backward through the DAG. "Backward" here means toward ancestors: if C-003 `depends_on` C-002, and C-002 `depends_on` C-001, then `claim_lineage("C-003")` returns `{C-001, C-002}`. The algorithm is a simple iterative DFS using an explicit stack (not recursion, to avoid stack overflow on deep graphs). The result answers "what is this claim built on?"

**`assumption_lineage(cid)`** computes all assumptions reachable from a claim and its ancestors. It first calls `claim_lineage` to get all ancestor claims, then collects every assumption directly referenced by any of those claims, then follows each assumption's own `depends_on` chain to capture presupposed assumptions. The result is the complete set of implicit premises the claim (and everything it builds on) takes as given. This is one of the most important queries in the system because it reveals invisible dependencies — a claim that looks self-contained may transitively rest on a dozen assumptions the researcher has never explicitly reviewed.

**`prediction_implicit_assumptions(pid)`** extends `assumption_lineage` to the prediction level. It unions `assumption_lineage` across all claims in the prediction's `claim_ids` set, then also expands `conditional_on` through assumption `depends_on` chains. The result is every assumption the prediction silently rests on, regardless of whether any of them are listed explicitly on the prediction itself. This is what the `validate_implicit_assumption_coverage` invariant uses to detect predictions that implicitly rest on empirical assumptions not listed in `tests_assumptions`.

**`refutation_impact(pid)`** answers: if this prediction is refuted, what is called into question? It returns three sets:
- `claim_ids`: the direct claims jointly implying this prediction.
- `claim_ancestors`: all ancestors of those claims via transitive `depends_on` closure — the entire theoretical chain the prediction was derived from.
- `implicit_assumptions`: all assumptions in the full derivation chain.

An AI agent calling this query after a `REFUTED` status transition gets a complete blast radius: every theoretical statement and every assumption that contributed to the now-falsified prediction.

**`assumption_support_status(aid)`** is the dual: given an assumption, what depends on it? It returns the claims that directly reference the assumption (`direct_claims`), every prediction whose derivation chain includes it (`dependent_predictions`), and the predictions explicitly designed to test it (`tested_by`). Computing `dependent_predictions` requires building a reverse index over all predictions' implicit assumption sets, which is O(P × I) where P is prediction count and I is average implicit assumption depth. The result tells a researcher: "if I revise this assumption, here is the full downstream conversation I need to have."

**`claims_depending_on_claim(cid)`** answers the forward question: if this claim is wrong, which downstream claims are built on it? It builds a reverse `depends_on` index — a dict mapping each claim ID to the set of claim IDs that depend on it — and then BFS from the target ID. The result is the forward blast radius in the claim DAG.

**`predictions_depending_on_claim(cid)`** extends this to predictions: it unions `claims_depending_on_claim(cid)` with the target claim itself, then finds every prediction whose `claim_ids` set intersects with that expanded set. Together with `claims_depending_on_claim`, it gives a complete picture of the damage if a claim is retracted.

**`parameter_impact(pid)`** computes the full blast radius of a parameter change: which analyses are stale (because `uses_parameters` includes this parameter), which claims carry a `parameter_constraints` annotation for this parameter, which claims are covered by the stale analyses, and which predictions depend on those claims. The result is a structured dict that the health-check and stale-detection services return to the caller without further computation.

### Domain Invariant Validators (`invariants.py`)

`invariants.py` contains ten pure validator functions with a uniform signature: each takes an `EpistemicWeb` and returns `list[Finding]`. There is no side effect. No mutation. `validate_all` composites them.

The distinction between the invariants in this file and the structural enforcement inside `web.py` matters:

- **Structural invariants** (referential integrity, acyclicity, bidirectional links) are enforced *inside* `EpistemicWeb` mutation methods at write time. They are guaranteed by construction. You cannot produce a web that violates them through the normal API.
- **Semantic invariants** (tier constraints, coverage gaps, testability rules) live in `invariants.py` and are checked *on demand*. They represent best-practice scientific discipline rules that may legitimately be incomplete during active research. A researcher might add a claim before adding the analyses that cover it; the system should not block that.

The ten validators:

**`validate_tier_constraints`** enforces the `ConfidenceTier` rules. A `FULLY_SPECIFIED` prediction with `free_params != 0` is a CRITICAL finding — the prediction's tier is fraudulent. A `CONDITIONAL` prediction missing `conditional_on` is a WARNING. A `MEASURED` prediction with no `observed` value is CRITICAL — the data either exists or the regime is set wrong.

**`validate_independence_semantics`** first checks that every prediction in an `IndependenceGroup.member_predictions` set back-references that group via `Prediction.independence_group` (the bidirectional link is enforced at mutation time, but this makes it auditable). It then checks pairwise separation completeness: for every pair of independence groups `(G-a, G-b)`, there must be a `PairwiseSeparation` record. If X groups exist, `X*(X-1)/2` separation records are required. Any missing pair is CRITICAL.

**`validate_coverage`** reports numerical claims with no linked analyses (INFO) and empirical assumptions with no `falsifiable_consequence` (WARNING). It also surfaces all `STRESSED` predictions as a group, since these represent active evidentiary tension and should not be silently submerged in a list of green checks.

**`validate_assumption_testability`** finds empirical assumptions that name a `falsifiable_consequence` but have no predictions in `tested_by`. The assumption claims it could be falsified but no prediction has been designed to test it. This is a WARNING: the researcher has identified the testability pathway but has not yet set up the corresponding prediction.

**`validate_retracted_claim_citations`** scans all predictions and all claims to find any that still reference a retracted claim in their `claim_ids` or `depends_on` sets. A `RETRACTED` claim should not remain in the derivation chain of an active prediction — doing so means the prediction's theoretical basis is known to be unsound. This is CRITICAL.

**`validate_implicit_assumption_coverage`** is the most computationally expensive validator. For each prediction it calls `prediction_implicit_assumptions` to find every assumption the prediction implicitly rests on, then checks whether any empirical assumptions in that set are absent from the prediction's explicit `tests_assumptions`. The finding is informational: it surfaces assumptions the prediction depends on that are not formally under active test, giving the researcher the full picture of what they are implicitly taking for granted.

**`validate_tests_conditional_overlap`** checks whether any prediction has the same assumption ID in both `tests_assumptions` and `conditional_on`. These are contradictory signals: `tests_assumptions` says "this prediction is designed to evaluate whether the assumption holds" while `conditional_on` says "this prediction is only valid if the assumption already holds." Listing the same assumption in both sets is a logical contradiction. CRITICAL.

**`validate_foundational_claim_deps`** checks claims whose `type` is `FOUNDATIONAL` for the presence of any `depends_on` entries. A foundational claim is definitionally primitive — it does not derive from any other claim in the web. Finding `depends_on` entries on a foundational claim is a CRITICAL contradiction.

**`validate_evidence_consistency`** checks that predictions in terminal states (`CONFIRMED` or `REFUTED`) have a linked analysis, and that analyses have at least one linked prediction. A confirmed prediction with no analysis is structurally suspicious — the confirmation is ungrounded. An analysis with no predictions is orphaned work with no traceability. It also verifies that `FIT_CHECK` predictions are not simultaneously classified as `NOVEL_PREDICTION` in `evidence_kind` — those two labels are mutually exclusive.

### The Abstract Ports (`ports.py`)

The kernel defines not just data structures, but also the shapes of the services the domain requires from the outside world. These are expressed as Python `Protocol` classes in `ports.py`. A `Protocol` specifies a structural interface: any class that provides the right methods satisfies the protocol without needing to explicitly declare it as an implementation.

```python
class WebRepository(Protocol):
    def load(self) -> EpistemicWeb: ...
    def save(self, web: EpistemicWeb) -> None: ...

class WebRenderer(Protocol):
    def render(self, web: EpistemicWeb) -> dict[str, str]: ...

class WebValidator(Protocol):
    def validate(self, web: EpistemicWeb) -> list[Finding]: ...

class TransactionLog(Protocol):
    def append(self, operation: str, identifier: str) -> str: ...

class ProseSync(Protocol):
    def sync(self, web: EpistemicWeb) -> dict[str, object]: ...
```

The kernel defines what it *needs*. The adapters layer defines how those needs are *satisfied*. The control plane uses the kernel's `Protocol` definitions without ever importing a concrete adapter class. This inversion is what allows the entire system to be tested without touching a filesystem: substitute an in-memory implementation for `WebRepository`, a stub for `TransactionLog`, and you have a fully functional, fully exercised control plane with zero I/O.

#### `ProseSync` — the Managed Prose Protocol

`ProseSync` is the protocol for a planned feature: **managed prose blocks**. The idea is that certain human-readable sections of a research document — a theory summary, a methods section, a list of current predictions — can be automatically regenerated from the canonical state of the epistemic web rather than maintained by hand. When a researcher adds a new prediction, the theory summary prose block should update automatically. When a claim is retracted, the relevant paragraph should reflect that.

`sync(web)` is the write operation: it regenerates all managed prose blocks from the current web state and returns a summary of what changed. The read/verification companion — `verify_prose_sync` — checks whether any managed prose has drifted from what the web would generate.

**Current status:** No concrete implementation of `ProseSync` exists yet. `factory.py` injects `_NullProseSync`, a no-op stub that satisfies the protocol interface and returns an empty dict. The gateway receives it, calls it, and the call does nothing. The protocol and the injection point are designed and in place; the concrete adapter that generates actual prose is future work.

---

## Project Configuration (`config.py`)

Between the kernel and the infrastructure sits `config.py`. It contains three dataclasses and two functions, and it is the **runtime configuration contract** for the entire system. It imports only the Python standard library.

`DesitterConfig` holds values parsed from the project's `desitter.toml` file: the directory name of the project data folder and any other project-level settings. All fields have safe defaults, so a missing or empty `desitter.toml` is valid.

`ProjectPaths` is a computed record of all filesystem paths the system will ever touch, derived once at startup:

```
workspace/
└── project/                       (configurable; default "project")
    ├── data/                      → context.paths.data_dir
    │   ├── claims.json            → context.paths.claims_json  (etc.)
    │   └── ...
    ├── views/                     → context.paths.views_dir
    └── .cache/
        ├── render.json            → context.paths.render_cache_file
        └── transaction_log.jsonl  → context.paths.transaction_log_file
```

Every path is computed once in `build_context()` and never re-derived. No service does `Path(context.workspace) / "project" / "data" / "claims.json"` inline — it reads `context.paths.data_dir`. This keeps filesystem layout knowledge in one place and makes it trivial to point everything at a temporary directory in tests.

`ProjectContext` bundles the workspace path, the parsed config, and the computed paths into a single object passed to every service:

```python
@dataclass
class ProjectContext:
    workspace: Path
    config:    DesitterConfig
    paths:     ProjectPaths
```

`load_config(workspace)` reads and parses the `desitter.toml` from the workspace root using `tomllib` (Python 3.11+ standard library) with a fallback to the `tomli` back-port for earlier versions. A missing file returns all defaults. `build_context(workspace, config)` constructs the `ProjectContext`. Both are called once at startup — in the MCP server's `create_server()` and in the CLI's root group — and the resulting context object is passed down through every service call for the duration of the process.

The rule: **no service reads from `os.environ`, no service opens files by path literals, no service has module-level globals that represent project state.** Data flows through `ProjectContext`. This is not idealism — it is the difference between a test that can point services at a temp directory and a test that cannot run without a real project tree on disk.

---

## The Adapter Layer (`adapters/`)

The adapters layer implements the abstract ports defined in `epistemic/ports.py`. It is the only layer in the system that speaks file formats, byte streams, and filesystem paths. Everything above it speaks `EpistemicWeb`.

### `JsonRepository`

`JsonRepository` implements `WebRepository`. It persists the epistemic web as a collection of JSON files under the project's `data/` directory — one file per entity type:

```
project/data/
├── claims.json
├── assumptions.json
├── predictions.json
├── analyses.json
├── theories.json
├── independence_groups.json
├── pairwise_separations.json
├── discoveries.json
├── dead_ends.json
└── parameters.json
```

`load()` reads and deserialises all ten files and assembles a fully hydrated `EpistemicWeb`. Missing files are treated as empty registries — a new project has no files at all and the repository returns an empty web, which is correct behaviour.

`save(web)` serialises the web back to disk **atomically**: for each entity type, it writes the JSON to a `.json.tmp` file in the same directory, then calls `tmp.replace(path)` — a POSIX atomic rename. If the process crashes mid-write, the on-disk state is always the complete previous version. No partial writes, no corrupted entity files.

The default serialisation uses `json.dumps(..., default=str)` which handles `date` objects, `Path` objects, and any other type that has a sensible string representation. `set` values are serialised as arrays (since JSON has no set type) and deserialised back to `set` on load.

### `TransactionLog`

`JsonTransactionLog` implements the `TransactionLog` protocol. Every mutation that reaches `repo.save()` is recorded as a JSONL (newline-delimited JSON) entry in `project/.cache/transaction_log.jsonl`. Each record contains:

- A UUID v4 transaction ID
- The operation type (`register/claim`, `set/prediction`, `transition/theory`, etc.)
- The entity identifier
- A UTC timestamp

The `append(operation, identifier)` method writes the record and returns the transaction ID. This ID is included in the `GatewayResult` returned to the caller and is the basis for audit trails. The append-only nature of the log also provides a foundation for future event replay.

### `MarkdownRenderer`

`MarkdownRenderer` implements `WebRenderer`. Given an `EpistemicWeb`, it generates a set of markdown surfaces — the human-readable views of the research project. The return value is `dict[str, str]`: a map from relative file path to rendered content. The renderer does not write files — it produces strings. The `views/render.py` service is responsible for deciding what to write and whether a render is needed (via SHA-256 fingerprinting described later).

---

## The Control Plane (`controlplane/`)

The control plane contains the system's core business services. It is the orchestration layer: it loads and saves the web through the `WebRepository` port, invokes the kernel's methods, calls the invariant validators, and writes provenance records to the transaction log. It contains no JSON parsing, no HTTP handling, no terminal output. Those concerns belong in the interface layer.

### The Gateway (`gateway.py`)

The Gateway is the **single mutation and query boundary** for the entire system. Both the CLI and the MCP server route all operations through it. There is no other path by which the epistemic web on disk can be changed.

The `Gateway` class receives its collaborators through constructor injection:

```python
class Gateway:
    def __init__(
        self,
        context:    ProjectContext,
        repo:       WebRepository,
        validator:  WebValidator,
        renderer:   WebRenderer,
        prose_sync: ProseSync,
        tx_log:     TransactionLog,
    ) -> None: ...
```

Every collaborator is declared as a protocol type. The gateway has no knowledge of `JsonRepository`, `MarkdownRenderer`, or any concrete adapter class. It works with the abstract interfaces and the concrete implementations are wired at startup by `factory.py`. This means the gateway can be fully unit-tested with in-memory stubs.

The gateway exposes six verbs:

```python
def register(resource, payload, *, dry_run=False)             → GatewayResult
def get(resource, identifier)                                  → GatewayResult
def list(resource, **filters)                                  → GatewayResult
def set(resource, identifier, payload, *, dry_run=False)       → GatewayResult
def transition(resource, identifier, new_status, *, dry_run=False) → GatewayResult
def query(query_type, **params)                                → GatewayResult
```

Every operation returns a `GatewayResult`:

```python
@dataclass
class GatewayResult:
    status:         str               # "ok" | "error" | "CLEAN" | "BLOCKED" | "dry_run"
    changed:        bool              # True if persistent state was modified
    message:        str               # human-readable summary
    findings:       list[Finding]     # empty for clean mutations
    transaction_id: str | None        # UUID set on successful mutations; None for reads
    data:           dict | None       # populated for get/list/query results
```

This envelope is the **contract** between the gateway and all interfaces. The MCP tool handlers serialise it to a dict. The CLI formatter renders it with Rich tables. A future REST endpoint would JSON-serialise it. The shape never changes — only how it is presented changes. This is the key property that allows any number of interface adapters to be written without touching the gateway.

#### Resource Alias Resolution

The gateway accepts flexible resource names in the `resource` parameter and resolves them through `GATEWAY_RESOURCE_ALIASES`:

```python
GATEWAY_RESOURCE_ALIASES = {
    "claim": "claim",  "claims": "claim",
    "prediction": "prediction",  "predictions": "prediction",
    "independence-group": "independence_group",
    "analyses": "analysis",
    # ... all forms for all ten types
}
```

An AI agent calling `register_resource("claims", ...)` and a CLI user calling `ds register claim ...` both resolve to the same canonical key `"claim"`. Adding a new entity type requires one entry in this table and nothing else in the dispatch machinery.

#### The Mutation Transaction Lifecycle

For `register`, `set`, and `transition` operations, the gateway executes the following sequence:

**Step 1: Resolve the resource alias.** `GATEWAY_RESOURCE_ALIASES.get(alias)` converts the caller-supplied string to a canonical key. Raises `KeyError` if unknown.

**Step 2: Load the current web.** `self._repo.load()` deserialises the current on-disk state into an `EpistemicWeb`. This is always a fresh load — the gateway does not cache the web between calls. For the CLI this is fine (each command is a new process). For the MCP server (a long-running process) this means every mutation reads from disk first, which ensures the MCP server is always working from the current state even if an external tool modified the files.

**Step 3: Parse and build the entity.** The gateway reads the payload dict and constructs the domain entity. Type coercions happen here: `set` fields populated from JSON arrays, `NewType` identifiers applied.

**Step 4: Mutate the web.** `web.register_*(entity)` (or `update_*`, or `transition_*`) is called. If this raises `EpistemicError` — broken reference, cycle, duplicate ID — the web was never modified (the copy-on-write semantics ensure this) and the gateway immediately returns a `GatewayResult(status="error", changed=False)`. The on-disk state is untouched.

**Step 5: Validate the new web.** `self._validator.validate(new_web)` runs all semantic invariant validators. If any finding is `CRITICAL`, the new web is discarded and the gateway returns an error result. The on-disk state remains the state from Step 2.

**Step 6: Honour dry-run.** If `dry_run=True`, the sequence stops here. The caller gets `GatewayResult(status="dry_run", changed=False, findings=[...])` — useful for pre-flight checks.

**Step 7: Write to disk.** `self._repo.save(new_web)` atomically replaces the on-disk state with the validated new web.

**Step 8: Log the transaction.** `self._tx_log.append(operation, entity_id)` appends a provenance record and returns a UUID transaction ID.

**Step 9: Check render triggers.** `automation.should_render(resource)` is consulted to decide whether the mutation warrants regenerating view surfaces. If it returns `True`, `render_all(context, new_web, renderer)` is called to update any stale markdown views. Only surfaces whose SHA fingerprint has changed are actually rewritten (see the Render Cache section under View Services). This step is a side-effect of the mutation — it does not affect the `GatewayResult`.

**Step 10: Return the result.** `GatewayResult(status="ok", changed=True, tx_id=...)`.

The critical property is that disk state can only change between Step 7 and Step 8. If the process crashes at Step 8, the disk state is still valid (the atomic rename from `JsonRepository.save` is complete) but the transaction is unlogged. This is an acceptable trade-off at research scale.

#### Read Operations: `get`, `list`, `query`

For read-only operations the gateway loads the web, extracts the requested data from the relevant dictionary or calls the appropriate traversal method, and returns a `GatewayResult` with `changed=False` and `data` populated. No validation is run. No transaction is logged. `query` maps named query types to web traversal methods — `"claim_lineage"` calls `web.claim_lineage(cid)`, `"refutation_impact"` calls `web.refutation_impact(pid)`, and so on.

### The Factory (`factory.py`)

`build_gateway(context)` is the **composition root**: the single place in the codebase where concrete adapter types are instantiated and injected into the `Gateway`. Both the CLI and the MCP server call `build_gateway(context)` once at startup, then never touch the adapters directly again. This function is the only place that imports concrete adapter classes:

```python
def build_gateway(context: ProjectContext) -> Gateway:
    repo       = JsonRepository(context.paths.data_dir)
    validator  = DomainValidator()
    renderer   = MarkdownRenderer()
    tx_log     = JsonTransactionLog(context.paths.transaction_log_file)
    prose_sync = _NullProseSync()          # no-op until prose adapter is implemented
    return Gateway(context, repo, validator, renderer, prose_sync, tx_log)
```

Having a single composition root means both interfaces always construct identical gateway instances. A bug fixed in `build_gateway` is fixed for every interface simultaneously. When the real `ProseSync` adapter is implemented, it is wired in here and nowhere else.

### Supporting Control-Plane Services

**`validate.py`** provides `validate_project(context, repo)` and `validate_structure(web)`. `validate_project` loads the web from the repository and runs `validate_all`. `validate_structure` runs only the structural validators (a subset of the full validator suite) and is the function called by the health check.

**`automation.py`** declares a **render-trigger policy table**: a mapping from resource type to the view surfaces that should be re-rendered after a successful mutation to that resource. The trigger table is intentionally decoupled from the gateway — the gateway calls `should_render(resource)` and acts on the answer, but has no knowledge of what the rules are or what surfaces exist. `should_render` is a pure function: given a resource name and optionally a custom trigger list, it returns `True` if any trigger matches.

```python
# automation.py
@dataclass
class RenderTrigger:
    resource: str
    surfaces: list[str] | None = None   # None = all surfaces

DEFAULT_RENDER_TRIGGERS = [
    RenderTrigger("claim"),
    RenderTrigger("assumption"),
    RenderTrigger("prediction"),
    RenderTrigger("analysis"),
    RenderTrigger("independence_group"),
    RenderTrigger("theory"),
    RenderTrigger("discovery"),
    RenderTrigger("dead_end"),
    RenderTrigger("parameter"),
]

def should_render(resource: str, triggers=None) -> bool:
    triggers = triggers or DEFAULT_RENDER_TRIGGERS
    return any(t.resource == resource for t in triggers)
```

Currently every mutation to any entity type triggers a full re-render, but the `surfaces` field makes it possible to later make this more selective — changing a `Parameter` could trigger only the "parameters" and "stale analyses" surfaces rather than the full view suite.

**`check.py`** provides staleness and consistency checks. `check_stale(context)` identifies view surfaces whose SHA-256 fingerprint in the render cache no longer matches the fingerprint that would be computed from the current web state. This is a file-comparison check, not a timestamp comparison: the system computes what the rendered output *would be* today and compares that hash against what was last written. A mismatch means the surface is stale and needs re-rendering. `check_refs(context, repo)` scans the on-disk registry for references to IDs that no longer exist — a cross-check against cases where a manual filesystem edit might have introduced a broken reference outside the normal gateway path.

**`export.py`** provides `export_json` and `export_markdown`: bulk export operations that produce a portable snapshot of the entire web, independent of the project's data directory structure.

---

## View Services (`views/`)

View services sit between the control plane and the interface layer. They are read-only from the web's perspective: they load, aggregate, and summarise — they never mutate the epistemic web. Their outputs are structured reports and rendered artifacts that both interfaces can present.

### Health Checks (`health.py`)

`run_health_check(context, repo, validator)` is the primary "everything OK?" operation. It:

1. Loads the web via `repo.load()`.
2. Runs all semantic invariant validators through `validator.validate(web)`.
3. Runs `check_stale(context)` to detect view surfaces that need re-rendering.
4. Runs `check_refs(context, repo)` to detect broken cross-references.
5. Aggregates all findings into a `HealthReport`.

`HealthReport.overall` is one of `"HEALTHY"`, `"WARNINGS"`, or `"CRITICAL"`. This single field is the machine-readable signal that CI, an AI agent, or a shell script can act on without parsing the full findings list. `critical_count` and `warning_count` are computed properties derived from the findings list.

### Project Status (`status.py`)

`get_status(context, repo)` produces a `ProjectStatus` snapshot: counts of entities by type, counts of predictions by tier and status, summary of outstanding structural gaps, and a timestamp. This is specifically designed to be the opening context for an AI agent session: one call gives the agent the complete landscape of the project without requiring it to make multiple queries.

`ProjectStatus` contains a `WebMetrics` object (see `metrics.py`) and a `health_summary` string. It can be serialised to a plain dict via `format_status_dict(status)` for MCP and JSON output.

### Metrics (`metrics.py`)

`compute_metrics(web)` produces quantitative summaries of the epistemic web: tier-A evidence ratios, assumption coverage rates, prediction resolution rates, and the like. `tier_a_evidence_summary(web)` specifically summarises the quantity and confirmation status of `FULLY_SPECIFIED` predictions, which is the primary scientific quality signal.

`WebMetrics` captures counts of each entity type, a `PredictionMetrics` breakdown (totals by status and tier, tier-A confirmed count, stressed prediction IDs), and lists of uncovered numerical claims and empirical assumptions without falsifiable consequences.

### Render Cache (`render.py`)

`render_all(context, web, renderer, force=False)` regenerates view surfaces with SHA-256-based incremental rendering. The process:

1. Load the stored fingerprint cache from `project/.cache/render.json` — a mapping of `surface_id → sha256_hash`.
2. For each view surface to render, compute what the rendered output *would be* by calling `renderer.render(web)`.
3. Hash the rendered content.
4. If the hash matches the stored fingerprint, skip the write.
5. If the hash differs (or `force=True`), write the content to disk and update the fingerprint cache.

The result is that a health check call — which internally calls `render_all` — does not rewrite every markdown file on every invocation. Only surfaces whose underlying data has actually changed are rewritten. On a project with many views and few mutations this saves significant I/O.

`compute_fingerprint(web)` computes a SHA-256 hash of the web's full serialisable state. This is the authoritative "has anything changed?" signal used by both `render_all` and `check_stale`.

---

## The Interface Layer (`interfaces/`)

The interface layer is the outermost ring of the system. It contains every surface through which a human or an AI agent interacts with deSitter: the CLI, the MCP server, and future surfaces such as a REST API or SDK. All surfaces are peers — there is no "primary" interface. Every interface is a **thin adapter**: it parses inputs, calls the same gateway and view service functions, and formats outputs. If a handler contains business logic, that logic is in the wrong place.

### The Command-Line Interface (`interfaces/cli/`)

`interfaces/cli/main.py` defines the Click command tree. At the top of the tree, the root `cli` group runs once per invocation: it reads the `--workspace` option (defaulting to the current working directory), calls `load_config` and `build_context`, and stores the resulting `ProjectContext` in Click's context object. Every subcommand below it retrieves the `ProjectContext` from the Click context and calls the appropriate gateway or view service.

```
ds register <resource>              →  gateway.register(resource, payload)
ds get      <resource> <id>         →  gateway.get(resource, id)
ds list     <resource>              →  gateway.list(resource)
ds set      <resource> <id>         →  gateway.set(resource, id, payload)
ds transition <resource> <id> <s>   →  gateway.transition(resource, id, s)
ds validate                         →  validate_project(context, repo)
ds health                           →  run_health_check(context, repo, validator)
ds status                           →  get_status(context, repo)
ds render [--force]                 →  render_all(context, web, renderer)
ds export [--format json|md]        →  export_json / export_markdown
ds init                             →  scaffold a new project workspace
```

`formatters.py` renders `GatewayResult`, `HealthReport`, and `ProjectStatus` objects using Rich — coloured tables, severity-coded finding lists, and structured panels. A `--json` flag bypasses the Rich renderer and writes the envelope dict as JSON to stdout, which allows shell scripts and CI systems to parse the output programmatically.

Throughout the CLI, the pattern is: parse → call → format. Nothing else. Any command that contains conditional logic about the *content* of parameters, or that calls more than one service function and merges the results, is violating the thin-adapter constraint and should be refactored to a service in `controlplane/`.

### The MCP Server (`interfaces/mcp/`)

MCP (Model Context Protocol) is an open protocol that lets AI agents call typed tools exposed by a server process — analogous to REST APIs but designed to be consumed by language model agents rather than humans. The agent calls `register_resource(resource="claim", payload={...})` as a structured tool call; the server executes the handler and returns a structured dict. No subprocess, no screen scraping, no parsing unstructured text.

`interfaces/mcp/server.py` constructs the FastMCP server. `create_server(workspace)` calls `load_config`, `build_context`, and `register_tools(server, context)`, then returns the configured server object. `run()` starts the server and blocks. The entry-point console script `ds-mcp` calls `run()`.

`interfaces/mcp/tools.py` registers the tool handlers using FastMCP's `@server.tool()` decorator. The full tool surface, which mirrors the CLI command surface:

```
register_resource   →  gateway.register(resource, payload, dry_run)
get_resource        →  gateway.get(resource, identifier)
list_resources      →  gateway.list(resource)
set_resource        →  gateway.set(resource, identifier, payload, dry_run)
transition_resource →  gateway.transition(resource, identifier, new_status, dry_run)
query_web           →  gateway.query(query_type, **params)
validate_web        →  validate_project(context, repo)
health_check        →  run_health_check(context, repo, validator)
project_status      →  get_status(context, repo)
render_views        →  render_all(context, web, renderer, force)
check_stale         →  check_stale(context)
check_refs          →  check_refs(context, repo)
export_web          →  export_json / export_markdown
```

Every handler follows the same pattern: call the service, call `_envelope(result)` to serialise the `GatewayResult` into a dict with the status-first convention, return the dict. The `_envelope` helper is the only formatting logic in the entire MCP interface.

The result dict always begins with `"status"`: `"ok"`, `"error"`, `"CLEAN"`, `"BLOCKED"`, or `"dry_run"`. This is the first thing an AI agent reads. A well-designed agent checks `result["status"]` before reading anything else.

#### How an AI Agent Uses the System

An agent operating on a research project will typically follow a session pattern like this:

1. Call `health_check()` to get the overall state and any critical findings.
2. Call `project_status()` to get entity counts, prediction tiers, and structural gaps.
3. Navigate specific entities via `get_resource` and `list_resources`.
4. Call `query_web("refutation_impact", pid="P-001")` to understand the blast radius of a status change.
5. Call `register_resource("prediction", {...}, dry_run=True)` to pre-flight a new prediction before committing it.
6. Call `register_resource("prediction", {...})` to commit the prediction.
7. Call `validate_web()` to confirm no new invariant violations were introduced.

At no point does the agent need to understand JSON file formats, directory structures, or transaction semantics. The tool surface is the entire API. The agent receives structured dicts back and can reason about them directly.

---

## Startup and Dependency Wiring

The full dependency tree is assembled exactly once, at the layer closest to the outside world. By the time any service method is called, every collaborator has been injected and no service needs to know how to construct its dependencies.

For the MCP server, the startup sequence is:

```
server.py: create_server(workspace)
    ↓
    load_config(workspace)            → DesitterConfig
    build_context(workspace, config)  → ProjectContext
    FastMCP(name="desitter")          → server
    register_tools(server, context)
        ↓
        factory.build_gateway(context)
            ↓
            JsonRepository(context.paths.data_dir)
            DomainValidator(validate_all)
            MarkdownRenderer()
            _NullProseSync()
            JsonTransactionLog(context.paths.transaction_log_file)
            →  Gateway(context, repo, validator, renderer, prose_sync, tx_log)
        @server.tool() for each tool function
    ↓
server.run()
```

For the CLI, the sequence is the same except that `build_gateway(context)` is called inside each command that needs mutation (rather than once at server startup), and the Click context object carries the `ProjectContext` between the root group and subcommands.

---

## Concurrency and Process Model

### The CLI

The CLI is a traditional UNIX process: one command, one execution, exit. Each `ds` invocation loads the web, performs one operation, writes back if needed, and terminates. There is no shared state between invocations; concurrency is not a concern for the CLI itself. Two simultaneous `ds` invocations on the same project would race at the filesystem level, but that scenario is rare for single-researcher projects and is an accepted trade-off at this scale.

### The MCP Server

The MCP server is a long-running process that communicates over stdio using the MCP protocol. FastMCP processes tool calls one at a time in its event loop — there is no thread pool and no parallelism within a single server instance. From the server's perspective, all tool calls are serialised.

However, a researcher may run multiple AI agents, or a single agent and the CLI simultaneously. Two processes could both hold a stale web snapshot and race to write:

```
Process A: load web  →  mutate in memory  →  validate  →  WRITE
Process B: load web  →  mutate in memory  →  validate  →  WRITE  ← overwrites A
```

The system's current model is **last-write-wins**. The second `repo.save()` atomically replaces the file, so the on-disk state is never corrupted (no partial writes), but Process A's mutation is silently lost. This is acceptable for single-researcher projects where simultaneous mutations from multiple agents are unusual.

What prevents corruption even in the race scenario:
- `JsonRepository.save` uses POSIX atomic rename, so the on-disk state is always a complete valid web — never a partially written file.
- The copy-on-write semantics mean each process works on its own snapshot and the web in memory is never in a partially-mutated state.
- The transaction log records what was committed, providing an audit trail.

A future hardening step could add optimistic concurrency control: record the transaction log entry count at load time, and before writing, verify that the count has not changed (i.e. no other process has committed since this load). If the count differs, reload and retry. No locking is needed; the transaction log provides the monotonic sequence number.

---

## Implementation Status

The architecture is fully specified and the kernel is fully implemented and tested. Several control-plane and view-service functions are stubs (`raise NotImplementedError`) that define the interface contract but have not yet been filled in. The table below shows what is complete and what is planned:

| Module / Feature | Status |
|---|---|
| `epistemic/types.py` — all enums and typed IDs | Complete |
| `epistemic/model.py` — all ten entity dataclasses | Complete |
| `epistemic/web.py` — all mutations, queries, traversals | Complete |
| `epistemic/invariants.py` — all ten validators | Complete |
| `epistemic/ports.py` — all protocols | Complete |
| `adapters/json_repository.py` — load, save, atomic rename | Complete |
| `adapters/transaction_log.py` — append, UUID generation | Complete |
| `adapters/markdown_renderer.py` — render to markdown | Complete |
| `config.py` — load_config, build_context | Complete |
| `controlplane/factory.py` — build_gateway | Complete |
| `controlplane/automation.py` — trigger table, should_render | Complete |
| `controlplane/gateway.py` — all six verbs | Stub |
| `controlplane/validate.py` — validate_project, validate_structure | Stub |
| `controlplane/check.py` — check_stale, check_refs | Stub |
| `controlplane/export.py` — export_json, export_markdown | Stub |
| `views/health.py` — run_health_check, HealthReport | Stub |
| `views/status.py` — get_status, ProjectStatus | Stub |
| `views/metrics.py` — compute_metrics, WebMetrics | Stub |
| `views/render.py` — render_all, fingerprinting | Stub |
| `interfaces/cli/main.py` — command tree | Stub |
| `interfaces/cli/formatters.py` — Rich output | Stub |
| `interfaces/mcp/server.py` — create_server, run | Complete |
| `interfaces/mcp/tools.py` — all tool handlers | Complete (delegates to gateway, which is stub) |
| `ProseSync` concrete adapter | Not started |
| `ds record` / `record_result` (analysis result recording) | Not started |
| Optimistic concurrency control | Not started |

"Stub" means the function signature, docstring, and return type are defined and the design intent is documented, but the body raises `NotImplementedError`. All stubs have passing type checks. The kernel and adapter tests are green.

---

## Layer Dependency Rules

Arrows point downward only. No layer may import from a layer above it. These rules are enforced by code review; `epistemic/` has it easiest since the standard library is its only conceivable dependency.

```
interfaces/*
    ↓
views/          controlplane/
    ↓               ↓
         config.py
             ↓
         adapters/
             ↓
         epistemic/
```

More precisely:

| Package | May import | May never import |
|---|---|---|
| `epistemic/` | standard library only | anything else |
| `adapters/` | `epistemic/`, standard library | `controlplane/`, `views/`, `interfaces/` |
| `config.py` | standard library only | anything else |
| `controlplane/` | `epistemic/`, `config`, adapters *via protocols only* | `views/`, `interfaces/` |
| `views/` | `controlplane/`, `epistemic/`, `config` | `interfaces/` |
| `interfaces/*` | all layers above | other `interfaces/*` packages |

The critical rule in the third-to-last row: `controlplane/` uses adapters *only through the abstract protocol types defined in `epistemic/ports.py`*. It never imports `JsonRepository` or any other concrete adapter class. Only `factory.py` (which sits inside `controlplane/` but acts as the composition root) wires concrete types together. This is what makes the control plane fully testable without the filesystem.

The last row rule — interfaces cannot import each other — means the CLI cannot import MCP tools and the MCP server cannot import CLI formatters. Each interface is self-contained. Shared output logic belongs in `views/`, shared formatting helpers common to all text outputs would belong in a shared `interfaces/_shared/` module.

---

## Key Design Principles

**The audit scaffold, not the reasoning engine.** deSitter surfaces structural facts; it never makes logical judgments. An AI agent calling `query_web("refutation_impact", pid="P-001")` gets a precise set of claims and assumptions called into question. What to *do* about them is the agent's problem. This keeps deSitter domain-neutral and applicable across disciplines.

**No execution.** deSitter does not run analyses. It records their provenance, captures their results when the researcher reports them, and tracks staleness. The `path` and `command` fields on `Analysis` are documentation. This is a deliberate constraint that eliminates a whole class of security concerns — no sandbox, no subprocess, no supply-chain risk from executing researcher code.

**One gateway.** All mutations flow through the `Gateway`. This means a bug fixed in the gateway is fixed for every interface simultaneously. A new resource type requires one entry in the alias table and nothing in any interface. The gateway is the product; the interfaces are presentations.

**Validate-after-write, not before.** The web is mutated in memory first, then validated, then written to disk. This ordering makes the structural invariants (enforced inside the web's methods) and the semantic invariants (checked by the domain validator) compose cleanly. The on-disk state is always the last state that passed full validation.

**Native Python collections.** Entity fields use `dict`, `set`, and `list` rather than immutable variants. The `EpistemicWeb` is the encapsulation boundary, not the type system. This choice keeps entity construction ergonomic in tests and reduces friction in Python's `dataclasses` ecosystem. The trade-off is that a caller who extracts an entity from the web and mutates its fields directly bypasses all invariant enforcement. This is prevented by convention and code review, not by the type system.

**ProjectContext carries data, not behaviour.** Services receive a `ProjectContext` object, not a service locator or a callback bag. Every service gets its file paths from `context.paths`. No service has module-level globals that represent project state. This makes services fully composable and fully testable: pass in a `ProjectContext` pointing at a temp directory and nothing touches the real filesystem.

---

## The Full Stack, in Summary

The following traces a single `register_resource("claim", {...})` call all the way from the AI agent to the filesystem and back:

```
AI agent tool call
    ↓
interfaces/mcp/tools.py  ::  register_resource(resource, payload, dry_run)
    │   parse, call _envelope, return dict
    ↓
controlplane/factory.py  ::  build_gateway(context)   [called once at startup]
    ↓
controlplane/gateway.py  ::  Gateway.register(resource, payload, dry_run=False)
    │   1. resolve_resource("claim")  →  "claim"
    │   2. repo.load()                →  EpistemicWeb (from disk)
    │   3. build Claim from payload
    │   4. web.register_claim(claim)  →  new_web  (or EpistemicError → return error)
    │      ├─ _copy()                 →  deep copy of all ten entity dicts
    │      ├─ DuplicateIdError if ID already exists
    │      ├─ BrokenReferenceError if any referenced ID is missing
    │      ├─ cycle check on depends_on DAG
    │      ├─ bidirectional link updates (Assumption.used_in_claims, etc.)
    │      └─ return new EpistemicWeb
    │   5. validator.validate(new_web)  →  list[Finding]
    │      └─ all ten invariant functions called
    │      if any CRITICAL  →  discard new_web, return GatewayResult(status="BLOCKED")
    │   6. if dry_run  →  return GatewayResult(status="dry_run")
    │   7. repo.save(new_web)
    │      └─ write to project/data/claims.json.tmp
    │      └─ atomic rename → project/data/claims.json
    │   8. tx_log.append("register/claim", claim_id)
    │      └─ append to project/.cache/transaction_log.jsonl
    │      └─ return UUID
    │   9. automation.should_render("claim")  →  True
    │      └─ render_all(context, new_web, renderer)
    │         └─ skip surfaces whose SHA fingerprint is unchanged
    │  10. return GatewayResult(status="ok", changed=True, tx_id=UUID)
    ↓
interfaces/mcp/tools.py  ::  _envelope(result)
    │   serialise GatewayResult to {"status": "ok", "changed": True, ...}
    ↓
AI agent receives structured dict
```

Every layer has exactly one responsibility. The kernel defines what is true. The adapters speak to storage. The gateway orchestrates. The interface formats for the consumer. Adding a new entity type means adding one dataclass in `model.py`, the methods in `web.py`, one entry in the gateway alias table, and the JSON serialisation in the repository — each in its correct layer, with no changes to anything else.
