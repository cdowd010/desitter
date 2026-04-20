# Episteme -- Tracker

Status: `[ ]` pending · `[~]` in progress · `[x]` done

**Target:** a researcher can `episteme.connect()` from a Python script or notebook, register and update all entity types, record analysis results, run queries, and get a health report. All without touching raw dicts or JSON files.

---

## Architecture Rules

These are execution constraints. Work that violates them should be rejected.

- All writes flow through `controlplane/gateway.py`. No second mutation path.
- The client changes calling conventions only. No business logic, no invariant bypass.
- `EpistemicGraph` is the kernel mutation surface. The Gateway orchestrates around it.
- `controlplane/` depends on abstractions from `epistemic/ports.py`. Concrete wiring stays in `factory.py`.
- Payload validation stays behind the `PayloadValidator` port. No inline validation in the Gateway.
- Fail fast: schema errors, broken references, and invariant failures surface before persistence.
- YAGNI: no concurrency control, indexing, CLI, or MCP until this target ships.

---

## Milestone 1: Epistemic Kernel -- COMPLETE

> 11 entity types, 31 validators, 7 transition tables, 112 tests.

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

- [x] `tests/epistemic/test_graph.py` -- 44 tests: register/update/remove round-trips for all entity types, transitions, backlinks, cycle detection, broken refs, duplicate IDs
- [x] `tests/epistemic/test_invariants.py` -- 62 tests: one or more tests for each of the 31 validators
- [x] `tests/controlplane/test_check.py` -- 1 test

---

## Milestone 2: Views -- COMPLETE

- [x] `views/evidence.py` -- `evidence_summary()` builds EvidenceSummary per hypothesis with ObservationDetail, PredictionDetail, AssumptionDetail, AnalysisDetail, ObjectiveDetail
- [x] `tests/views/test_evidence.py` -- 5 tests

---

## Milestone 3: Gateway

> requires: Epistemic Kernel

- [x] Gateway metadata: `_gateway_catalog.py` (RESOURCE_SPECS, QUERY_SPECS), `_gateway_results.py` (GatewayResult)
- [x] `controlplane/validate.py` -- `DomainValidator.validate()` delegates to `validate_all`
- [ ] `validate_project(graph, extra_validators)` -- run `DomainValidator` plus any extras, return combined findings
- [ ] `Gateway.__init__` -- store graph, validator, payload_validator
- [ ] `Gateway.graph` property -- return current in-memory graph
- [ ] `Gateway.resolve_resource` -- validate and return canonical resource key
- [ ] `Gateway._resource_spec` -- look up ResourceSpec by resource key
- [ ] `Gateway._typed_identifier` -- coerce string ID to NewType
- [ ] `Gateway._lookup_entity` -- find entity by resource key and ID
- [ ] `Gateway._validate_payload` -- delegate to PayloadValidator if configured
- [ ] `Gateway._matches_filters` -- test serialized entity dict against filter predicates
- [ ] `Gateway._error_result` -- construct error GatewayResult
- [ ] `Gateway._finalize_mutation` -- run validators on new graph; CRITICAL blocks; swap on success
- [ ] `Gateway.register` -- validate payload, build entity, call kernel, finalize
- [ ] `Gateway.get` -- look up entity, serialize, return
- [ ] `Gateway.list` -- collect all entities of type, filter, serialize, return
- [ ] `Gateway.set` -- fetch existing, merge payload, rebuild entity, call kernel, finalize
- [ ] `Gateway.transition` -- fetch existing, call kernel transition, finalize
- [ ] `Gateway.query` -- resolve QuerySpec, coerce params, call graph method, serialize, return
- [ ] `Gateway.record_analysis_result` -- narrow wrapper over `EpistemicGraph.record_analysis_result`

### Factory

- [ ] `build_gateway(graph, *, payload_validator)` -- instantiate `DomainValidator`, construct and return `Gateway`

### Gateway Tests

- [ ] Register round-trip for at least one entity (hypothesis)
- [ ] get / list / set / transition round-trips
- [ ] Query round-trips (hypothesis_lineage, refutation_impact, parameter_impact)
- [ ] CRITICAL finding blocks mutation, graph unchanged
- [ ] dry_run returns findings without mutating
- [ ] Broken reference returns error result
- [ ] Duplicate ID returns error result
- [ ] record_analysis_result round-trip

---

## Milestone 4: Adapters

> requires: Epistemic Kernel

- [ ] `adapters/json_repository.py` -- load/save EpistemicGraph to JSON
- [ ] `adapters/transaction_log.py` -- append-only mutation journal; extend protocol with timestamp and agent_id fields
- [ ] `adapters/payload_validator.py` -- schema validation against payload specs

---

## Milestone 5: Config

- [x] Config dataclasses: `EpistemeConfig`, `ProjectPaths`, `ProjectContext`
- [~] `load_config(workspace: Path) -> EpistemeConfig` -- parse `episteme.toml`; return defaults if absent
- [ ] `build_context(workspace: Path, config: EpistemeConfig) -> ProjectContext` -- derive all paths

---

## Milestone 6: Client

> requires: Gateway, Adapters, Config

- [ ] `_EpistemeClientCore.__init__(gateway, *, repo)` -- store gateway and repo
- [ ] `_EpistemeClientCore.gateway` property
- [ ] `_EpistemeClientCore.save()` -- call `repo.save(gateway.graph)` if repo present
- [ ] `_EpistemeClientCore.__enter__` / `__exit__` -- context manager; auto-save on exit
- [ ] `_EpistemeClientCore.register(resource, *, dry_run, **payload)` -> `ClientResult`
- [ ] `_EpistemeClientCore.get(resource, identifier)` -> `ClientResult`
- [ ] `_EpistemeClientCore.list(resource, **filters)` -> `ClientResult`
- [ ] `_EpistemeClientCore.set(resource, identifier, *, dry_run, **payload)` -> `ClientResult`
- [ ] `_EpistemeClientCore.transition(resource, identifier, new_status, *, dry_run)` -> `ClientResult`
- [ ] `_EpistemeClientCore.query(query_type, **params)` -> `ClientResult`
- [ ] `_EpistemeClientCore._invoke_gateway` -- call gateway method, wrap unexpected errors
- [ ] `_EpistemeClientCore._handle_resource_result` -- convert GatewayResult to ClientResult
- [ ] `connect(*, repo, graph)` -- load config, build graph, build gateway, return EpistemeClient
- [ ] `_without_none(**payload)` -- strip None values from payload dict

### Typed Helpers

All three helper mixins have signatures but raise `NotImplementedError`. Implement all as thin wrappers over `self.register(...)`, `self.get(...)`, `self.list(...)`, `self.set(...)`, `self.transition(...)`.

**`_hypothesis.py`** (Hypotheses, Assumptions, Predictions)
- [ ] `register_hypothesis`, `get_hypothesis`, `list_hypotheses`, `set_hypothesis`, `transition_hypothesis`
- [ ] `register_assumption`, `get_assumption`, `list_assumptions`, `set_assumption`
- [ ] `register_prediction`, `get_prediction`, `list_predictions`, `set_prediction`, `transition_prediction`

**`_structure.py`** (Parameters, IndependenceGroups, PairwiseSeparations, Analyses, Observations)
- [ ] `register_parameter`, `get_parameter`, `list_parameters`, `set_parameter`
- [ ] `register_independence_group`, `get_independence_group`, `list_independence_groups`, `set_independence_group`
- [ ] `register_pairwise_separation`, `get_pairwise_separation`, `list_pairwise_separations`
- [ ] `register_analysis`, `get_analysis`, `list_analyses`, `set_analysis`
- [ ] `register_observation`, `get_observation`, `list_observations`, `set_observation`, `transition_observation`
- [ ] `record_analysis_result(analysis_id, result, *, sha, date)` -- delegate to gateway

**`_registry.py`** (Objectives, Discoveries, DeadEnds)
- [ ] `register_objective`, `get_objective`, `list_objectives`, `set_objective`, `transition_objective`
- [ ] `register_discovery`, `get_discovery`, `list_discoveries`, `set_discovery`, `transition_discovery`
- [ ] `register_dead_end`, `get_dead_end`, `list_dead_ends`, `set_dead_end`, `transition_dead_end`

### Client Tests

- [ ] `connect()` returns a working client against a temp workspace
- [ ] register_* / get_* / list_* helpers for all entity types
- [ ] set_* helpers for all entity types
- [ ] transition_* helpers for status-bearing entities
- [ ] record_analysis_result round-trip through client
- [ ] dry_run=True validates without writing
- [ ] Schema validation errors surface as ClientResult errors, not exceptions

---

## Milestone 7: Health View

> requires: Validate

- [ ] `run_health_check(graph, validator)` in `views/health.py` -- run validator, compute overall status, return `HealthReport`
- [ ] Test: returns HEALTHY on a clean graph
- [ ] Test: returns WARNING / CRITICAL on a graph with violations

---

## Milestone 8: AI Agency Foundations

> requires: Gateway, Adapters, Client

These items enable AI agents to use Episteme as a research world model. The kernel and architecture already support this; these are additive extensions.

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

## Exit Criteria

Every item below must be true before the Python API target is closed:

- [ ] `client = episteme.connect()` works from a Python script in a real workspace directory
- [ ] All 11 entity types can be registered through typed keyword-argument helpers
- [ ] All 11 entity types can be updated through typed `set_*` helpers
- [ ] All status-bearing entities can be transitioned through typed helpers
- [ ] Analysis results can be recorded programmatically via `record_analysis_result`
- [ ] All named queries return structured `ClientResult` objects suitable for notebooks
- [ ] `run_health_check` returns a `HealthReport` with correct overall status
- [ ] Structured `AdjudicationRationale` type replaces plain string on `Prediction`
- [ ] `validate_independence_of_adjudication` flags self-attested high-stakes transitions
- [ ] Transaction log adapter records agent_id and timestamp per mutation
- [ ] MCP tools enforce atomic observation registration (no split run/register)
- [ ] Validation failures (schema errors, broken refs, CRITICAL invariants) fail fast without writing
- [ ] dry_run=True validates and returns findings without mutating the graph
- [ ] All of the above is covered by automated tests

---

## Deferred

Everything below is deferred until the exit criteria above are met:

- CLI command handlers
- MCP server and tools
- `controlplane/check.py` (staleness detection beyond what tests cover)
- `controlplane/render.py` and `controlplane/export.py`
- `controlplane/prose.py`
- `views/status.py` and `views/metrics.py`
- Query performance indexing
- Optimistic concurrency control
