# Episteme -- Tracker

Status: `[ ]` pending · `[~]` in progress · `[x]` done

**Target:** a researcher can `episteme.connect()` from a Python script or
notebook, register and update all entity types, record analysis results, run
queries, validate the graph, and get a health report -- all without touching
raw dicts or JSON files. The architecture also supports AI agents as
first-class users through the same Gateway and invariant system, but the
Python API is the first shipping interface.

---

## Architecture Rules

These are execution constraints. Work that violates them should be rejected.

- All writes flow through `controlplane/gateway.py`. No second mutation path.
- The client changes calling conventions only. No business logic, no invariant bypass.
- `EpistemicGraph` is the kernel mutation surface. The Gateway orchestrates around it.
- `controlplane/` depends on abstractions from `epistemic/ports.py`. Concrete wiring stays in `factory.py`.
- Views depend only on kernel protocols (`EpistemicGraphPort`, `GraphValidator`). No imports from controlplane or client.
- Payload validation stays behind the `PayloadValidator` port. No inline validation in the Gateway.
- Fail fast: schema errors, broken references, and invariant failures surface before persistence.
- YAGNI: no concurrency control, indexing, CLI, or MCP until this target ships.

---

## Milestone 1: Epistemic Kernel -- COMPLETE

> 12 entity types, 33 validators, 8 transition tables, 133 tests.

- [x] `types.py` -- 11 typed IDs, 19 enums, 7 transition tables, Finding, 3 typed query dataclasses (RefutationImpact, AssumptionSupportStatus, ParameterImpact)
- [x] `model.py` -- 11 entity dataclasses: Hypothesis, Assumption, Prediction, Observation, Analysis, Parameter, Objective, Discovery, DeadEnd, IndependenceGroup, PairwiseSeparation
- [x] `graph.py` -- EpistemicGraph aggregate root, copy-on-write, all mutations, queries, transitions, bidirectional backlink maintenance
- [x] `invariants.py` -- 31 pure validator functions + validate_all + validate_prediction_transition
- [x] `errors.py` -- EpistemicError, DuplicateIdError, BrokenReferenceError, CycleError, InvariantViolation
- [x] `codec.py` -- introspection-based serialization
- [x] `ports.py` -- Protocol re-exports
- [x] `_ports_graph.py` -- EpistemicGraphPort, GraphRepository
- [x] `_ports_services.py` -- GraphValidator, ProseSync, TransactionLog, PayloadValidator
- [x] `_ports_artifacts.py` -- Artifact, ArtifactSink, GraphExporter, GraphRenderer

### Tests (Milestone 1)

- [x] `tests/epistemic/test_graph.py` -- 65 tests: register/update/remove round-trips for all entity types, transitions, backlinks, cycle detection, broken refs, duplicate IDs
- [x] `tests/epistemic/test_invariants.py` -- 67 tests: one or more tests for each of the 31 validators
- [x] `tests/controlplane/test_check.py` -- 1 test

---

## Milestone 2: Evidence View -- COMPLETE

- [x] `views/evidence.py` -- `evidence_summary()` builds EvidenceSummary per hypothesis with ObservationDetail, PredictionDetail, AssumptionDetail, AnalysisDetail, ObjectiveDetail
- [x] `tests/views/test_evidence.py` -- 5 tests

> Remaining views (health, status, metrics) tracked in Milestone 7.

---

## Milestone 3: Gateway -- COMPLETE

> requires: Epistemic Kernel

- [x] Gateway metadata: `_gateway_catalog.py` (RESOURCE_SPECS, QUERY_SPECS), `_gateway_results.py` (GatewayResult)
- [x] `controlplane/validate.py` -- `DomainValidator.validate()` delegates to `validate_all`
- [x] `Gateway.__init__` -- store graph, validator, payload_validator
- [x] `Gateway.graph` property -- return current in-memory graph
- [x] `Gateway.resolve_resource` -- validate and return canonical resource key
- [x] `Gateway._resource_spec` -- look up ResourceSpec by resource key
- [x] `Gateway._typed_identifier` -- coerce string ID to NewType
- [x] `Gateway._lookup_entity` -- find entity by resource key and ID
- [x] `Gateway._validate_payload` -- delegate to PayloadValidator if configured
- [x] `Gateway._matches_filters` -- test serialized entity dict against filter predicates
- [x] `Gateway._error_result` -- construct error GatewayResult
- [x] `Gateway._finalize_mutation` -- run validators on new graph; CRITICAL blocks; swap on success; hydrate entity data; support `dry_run`
- [x] `Gateway.register(resource, payload, *, dry_run)` -- validate payload, build entity, call kernel, finalize
- [x] `Gateway.get` -- look up entity, serialize, return
- [x] `Gateway.list` -- collect all entities of type, filter, serialize, return
- [x] `Gateway.set(resource, identifier, payload, *, dry_run)` -- fetch existing, merge payload, rebuild entity, call kernel, finalize
- [x] `Gateway.transition(resource, identifier, new_status, *, dry_run)` -- fetch existing, call kernel transition, finalize
- [x] `Gateway.query` -- resolve QuerySpec, coerce params, call graph method, serialize, return
- [x] `build_gateway(graph, *, payload_validator)` -- instantiate `DomainValidator`, construct and return `Gateway`

### Tests (Milestone 3)

- [x] `tests/controlplane/test_gateway.py` -- 64 tests: register/get/list/set/transition/query round-trips; CRITICAL blocks; dry_run; broken refs; duplicate IDs; payload validation; filter matching

---

## Milestone 4: Adapters -- COMPLETE

> requires: Epistemic Kernel, ports.py protocols

- [x] `adapters/json_repository.py` -- load/save EpistemicGraph to JSON via `GraphRepository` protocol
- [x] `adapters/transaction_log.py` -- append-only JSONL mutation journal via `TransactionLog` protocol
- [x] `adapters/payload_validator.py` -- schema validation against payload specs via `PayloadValidator` protocol

### Tests (Milestone 4)

- [x] `tests/adapters/test_json_repository.py` -- 14 tests
- [x] `tests/adapters/test_payload_validator.py` -- 13 tests
- [x] `tests/adapters/test_transaction_log.py` -- 12 tests

---

## Milestone 5: Config -- COMPLETE

- [x] Config dataclasses: `EpistemeConfig`, `ProjectPaths`, `ProjectContext`
- [x] `load_config(workspace: Path) -> EpistemeConfig` -- parse `episteme.toml`; return defaults if absent
- [x] `build_context(workspace: Path, config: EpistemeConfig) -> ProjectContext` -- derive all paths
- [x] `validate_workspace(context: ProjectContext) -> list[Finding]` -- sanity-check workspace paths

---

## Milestone 6: Client -- COMPLETE

> requires: Gateway, Adapters, Config

- [x] `_EpistemeClientCore.__init__(gateway, *, repo)` -- store gateway and repo
- [x] `_EpistemeClientCore.gateway` property
- [x] `_EpistemeClientCore.save()` -- call `repo.save(gateway.graph)` if repo present
- [x] `_EpistemeClientCore.__enter__` / `__exit__` -- context manager; auto-save on exit
- [x] `_EpistemeClientCore.register / get / list / set / transition / query` -- generic verbs returning `ClientResult`
- [x] `_EpistemeClientCore.validate(*, extra_validators)` -> `list[Finding]`
- [x] `_EpistemeClientCore._invoke_gateway` / `_handle_resource_result` / `_handle_resource_list_result` / `_handle_query_result`
- [x] `connect(*, repo, graph, workspace)` -- build gateway from graph, repo, or workspace config; return `EpistemeClient`
- [x] `_hypothesis.py` -- register/get/list/set/transition for hypothesis, assumption, prediction, analysis, observation
- [x] `_structure.py` -- register/get/list/set for parameter, independence_group, pairwise_separation
- [x] `_registry.py` -- register/get/list/set/transition for objective, discovery, dead_end

### Tests (Milestone 6)

- [x] `tests/client/test_client.py` -- 63 tests: connect() branches, lifecycle, all generic verbs, all 10 typed helper families, error handling, dry_run

---

## Milestone 7: Views -- Health, Status, Metrics

> requires: Epistemic Kernel, DomainValidator (from M3 validate.py)

These views depend only on kernel protocols. They can be built anytime after
the kernel, but health in particular is needed for the target.

### Health

- [ ] `run_health_check(graph, validator)` in `views/health.py` -- run validator, compute overall status, return `HealthReport`
- [ ] Test: returns HEALTHY on a clean graph
- [ ] Test: returns WARNING / CRITICAL on a graph with violations

### Status

- [ ] `get_status(graph)` in `views/status.py` -- entity counts, coverage statistics, overall project state → `ProjectStatus`
- [ ] `format_status_dict(status)` -- serialize for display
- [ ] Tests: counts match registered entities; coverage stats correct

### Metrics

- [ ] `compute_metrics(graph)` in `views/metrics.py` -- prediction outcomes, coverage ratios → `PredictionMetrics`, `GraphMetrics`
- [ ] `tier_a_evidence_summary(graph)` -- summary of fully-specified evidence
- [ ] Tests: metrics correct for known graph states

---

## Milestone 8: Interfaces

> requires: Client, Views
> Deferred per YAGNI until the Python API target ships.

### CLI

- [ ] Click-based command group: `episteme health`, `episteme validate`, `episteme status`
- [ ] `--json` flag on all commands for machine-readable output
- [ ] Rich terminal formatting for human-readable output

### MCP Server

- [ ] Expose Gateway verbs (register, get, list, set, transition, query) as MCP tools
- [ ] AI agents operate under the same invariant rules and lifecycle constraints as human users
- [ ] No reduced or simulated interface -- agents are full participants

---

## Milestone 9: AI Agency Foundations

> requires: Gateway, Adapters, Client, Interfaces

These items enable AI agents to use Episteme as a research world model. The
kernel and architecture already support this; these are additive extensions.

### Structured Adjudication

- [ ] Define `AdjudicationRationale` type: `text`, `evidence_refs` (content-addressed hashes), `authored_by`
- [ ] Replace `Prediction.adjudication_rationale: str | None` with `AdjudicationRationale | None`
- [ ] Update `validate_adjudication_rationale` to check structured fields
- [ ] `validate_independence_of_adjudication` -- WARNING when `authored_by` on a high-stakes transition matches the agent that registered the evidence

### Transaction Log Provenance

- [ ] Extend `TransactionLog.append` protocol to include timestamp, payload hash, and agent_id
- [ ] Merkle-linked log adapter for tamper-evident history (swarm use case)

### Atomic Tooling (MCP layer)

- [ ] Design single experiment+register MCP tool that atomically registers an observation when an analysis runs
- [ ] Ensure no separate "run then optionally register" path exists for agents

### Concurrent Write Coordination

- [ ] `GraphRepository.save_if_version(graph, expected_version)` -- CAS-style save using existing `EpistemicGraph.version` field
- [ ] Gateway-level retry or merge strategy on version conflict

### Agent Interaction Patterns

- [ ] QC agent pattern: read-only graph access + validator suite as a standalone tool
- [ ] Debater pattern: multiple agents writing to the same graph with independence group mediation
- [ ] Degradation strategy primitives: retract, dead-end, supersede, escalate documented as agent policy building blocks

---

## Possible Future Work: Dataset Entity

> Evaluate whether Dataset is needed or if recording analysis provenance (script path, SHA, date) is sufficient.

- [ ] `DatasetId` NewType, `DatasetStatus` enum (`ACTIVE`, `DEPRECATED`, `SUPERSEDED`) -- `types.py`
- [ ] `Dataset` dataclass (`id`, `name`, `version`, `description`, `path`, `used_in_analyses`) -- `model.py`
- [ ] `Analysis.uses_datasets: set[DatasetId]` field -- `model.py`
- [ ] `register_dataset`, `update_dataset`, `remove_dataset` -- `graph.py`
- [ ] Backlink maintenance: `Analysis.uses_datasets` <-> `Dataset.used_in_analyses` -- `graph.py`
- [ ] `validate_deprecated_dataset_usage` -- WARNING: analysis using a DEPRECATED or SUPERSEDED dataset -- `invariants.py`
- [ ] Client helpers: `register_dataset`, `get_dataset`, `list_datasets`, `set_dataset`

---

## Exit Criteria (Python API Target)

Every item below must be true before the Python API target is closed.
Milestones 1--7 are in scope. Milestones 8--9 are post-target.

- [ ] `client = episteme.connect()` works from a Python script in a real workspace directory
- [ ] All 11 entity types can be registered through typed keyword-argument helpers
- [ ] All 11 entity types can be updated through typed `set_*` helpers
- [ ] All status-bearing entities can be transitioned through typed helpers
- [ ] Analysis results can be recorded programmatically via `record_analysis_result`
- [ ] All named queries return structured `ClientResult` objects suitable for notebooks
- [ ] `client.validate()` runs the full invariant suite and returns findings
- [ ] `run_health_check` returns a `HealthReport` with correct overall status
- [ ] Graph persists to JSON and loads back without data loss
- [ ] Validation failures (schema errors, broken refs, CRITICAL invariants) fail fast without writing
- [ ] dry_run=True validates and returns findings without mutating the graph
- [ ] All of the above is covered by automated tests

---

## Deferred

Acknowledged stubs that exist in the codebase but are not needed for the
Python API target. Each slots into a future milestone when the need is proven.

- `controlplane/prose.py` -- managed-prose synchronization
- `controlplane/render.py` -- incremental rendering and fingerprint caching
- `controlplane/export.py` -- artifact export orchestration
- `controlplane/check.py: check_refs()` -- referential integrity diagnostic (check_stale is implemented)
- Event sourcing or result-history model
- Query-performance indexing
- Rich interactive CLI (completions, dashboards)
- REST API
