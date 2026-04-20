# deSitter — Tracker

Status: `[ ]` pending · `[~]` in progress · `[x]` done

**Target:** a researcher can `ds.connect()` from a Python script or notebook, register and update all entity types, record analysis results, run queries, and get a health report — all without touching raw dicts or JSON files.

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

## Epistemic Kernel

- [x] `types.py`, `model.py`, `graph.py`, `invariants.py`, `errors.py`, `codec.py`, `ports.py`

### ResearchObjective

- [ ] `ResearchObjectiveId` NewType, `ResearchObjectiveStatus` enum (`OPEN`, `NARROWED`, `TARGETED`, `ACHIEVED`, `ABANDONED`) — `types.py`
- [ ] `ResearchObjective` dataclass (`id`, `statement`, `domain`, `status`, `candidate_theories`, `related_discoveries`, `notes`) — `model.py`
- [ ] `EpistemicGraph.research_objectives` collection field — `graph.py`
- [ ] `register_research_objective`, `update_research_objective`, `remove_research_objective`, `transition_research_objective` — `graph.py`
- [ ] `remove_theory`, `remove_discovery` — scrub ID from `ResearchObjective` soft links — `graph.py`
- [ ] `EpistemicGraphPort` — add `research_objectives` attribute and new method signatures — `_ports_graph.py`

### Dataset

- [ ] `DatasetId` NewType, `DatasetStatus` enum (`ACTIVE`, `DEPRECATED`, `SUPERSEDED`) — `types.py`
- [ ] `Dataset` dataclass (`id`, `name`, `version`, `description`, `path`, `used_in_analyses`) — `model.py`
- [ ] `Analysis` — add `uses_datasets: set[DatasetId]` field — `model.py`
- [ ] `EpistemicGraph.datasets` collection field — `graph.py`
- [ ] `register_dataset`, `update_dataset`, `remove_dataset` — `graph.py`
- [ ] `register_analysis`, `update_analysis`, `remove_analysis` — handle `uses_datasets` ↔ `Dataset.used_in_analyses` backlinks — `graph.py`
- [ ] `EpistemicGraphPort` — add `datasets` attribute and new method signatures — `_ports_graph.py`

### Invariants

- [ ] `validate_adjudicated_prediction_no_analysis` — WARNING: CONFIRMED/STRESSED/REFUTED prediction with `analysis = None` — `invariants.py`
- [ ] `validate_revised_claim_downstream_impact` — WARNING: predictions or claims that cite a REVISED claim — `invariants.py`
- [ ] `validate_active_theory_claims_retracted` — WARNING: ACTIVE theory whose entire `related_claims` set is RETRACTED or REVISED — `invariants.py`
- [ ] `validate_deprecated_dataset_usage` — WARNING: analysis using a DEPRECATED or SUPERSEDED dataset — `invariants.py`
- [ ] `validate_research_objective_status_consistency` — WARNING: TARGETED with no viable theories; INFO: OPEN with candidate theories — `invariants.py`
- [ ] `validate_abandoned_objective_active_theories` — INFO: ABANDONED objective with ACTIVE or REFINED candidate theories — `invariants.py`
- [ ] Register all new validators in `validate_all()` — `invariants.py`

---

## Config

- [x] Config dataclasses: `DesitterConfig`, `ProjectPaths`, `ProjectContext`
- [ ] `load_config(workspace: Path) -> DesitterConfig` — parse `desitter.toml`; return defaults if absent
- [ ] `build_context(workspace: Path, config: DesitterConfig) -> ProjectContext` — derive all paths

---

## Adapters

> requires: Epistemic Kernel

- [x] `json_repository.py` (load/save)
- [x] `transaction_log.py`
- [x] `payload_validator.py`

---

## Validate

> requires: Epistemic Kernel

- [x] `DomainValidator.validate()` in `controlplane/validate.py`
- [ ] `validate_project(graph, extra_validators)` — run `DomainValidator` plus any extras, return combined findings

---

## Gateway

> requires: Config, Adapters

- [x] Gateway metadata tables: `_gateway_catalog.py` (RESOURCE_SPECS, QUERY_SPECS), `_gateway_results.py` (GatewayResult)
- [ ] `_gateway_catalog.py` — add `ResearchObjective` ResourceSpec (with transition)
- [ ] `_gateway_catalog.py` — add `Dataset` ResourceSpec
- [ ] `__init__` — store graph, validator, payload_validator
- [ ] `graph` property — return current in-memory graph
- [ ] `resolve_resource` — validate and return canonical resource key
- [ ] `_resource_spec` — look up ResourceSpec by resource key
- [ ] `_typed_identifier` — coerce string ID to resource's NewType
- [ ] `_lookup_entity` — find entity in graph by resource key and string ID
- [ ] `_validate_payload` — delegate to PayloadValidator if configured
- [ ] `_matches_filters` — test serialized entity dict against filter predicates
- [ ] `_error_result` — construct error GatewayResult
- [ ] `_finalize_mutation` — run validators on new graph; CRITICAL blocks; swap on success
- [ ] `register` — validate payload → build entity → call kernel → _finalize_mutation
- [ ] `get` — look up entity → serialize → return
- [ ] `list` — collect all entities of type → filter → serialize → return
- [ ] `set` — fetch existing → merge payload → rebuild entity → call kernel → _finalize_mutation
- [ ] `transition` — fetch existing → call kernel transition method → _finalize_mutation
- [ ] `query` — resolve QuerySpec → coerce params → call graph method → serialize → return
- [ ] `record_analysis_result` — narrow wrapper over `EpistemicGraph.record_analysis_result`

---

## Factory

> requires: Gateway, Validate, Adapters

- [ ] `build_gateway(graph, *, payload_validator)` — instantiate `DomainValidator`, construct and return `Gateway`

---

## Client

> requires: Factory, Config

- [x] Typed helper signatures declared in `client/_hypothesis.py`, `_registry.py`, `_structure.py`
- [ ] `_DeSitterClientCore.__init__(gateway, *, repo)` — store gateway and repo
- [ ] `_DeSitterClientCore.gateway` property
- [ ] `_DeSitterClientCore.save()` — call `repo.save(gateway.graph)` if repo present
- [ ] `_DeSitterClientCore.__enter__` / `__exit__` — context manager; auto-save on exit
- [ ] `_DeSitterClientCore.register(resource, *, dry_run, **payload)` → `ClientResult`
- [ ] `_DeSitterClientCore.get(resource, identifier)` → `ClientResult`
- [ ] `_DeSitterClientCore.list(resource, **filters)` → `ClientResult`
- [ ] `_DeSitterClientCore.set(resource, identifier, *, dry_run, **payload)` → `ClientResult`
- [ ] `_DeSitterClientCore.transition(resource, identifier, new_status, *, dry_run)` → `ClientResult`
- [ ] `_DeSitterClientCore.query(query_type, **params)` → `ClientResult`
- [ ] `_DeSitterClientCore._invoke_gateway` — call gateway method, wrap unexpected errors
- [ ] `_DeSitterClientCore._handle_resource_result` — convert GatewayResult to ClientResult
- [ ] `connect(*, repo, graph)` — load config + context, build graph via repo or empty, build gateway via factory, return DeSitterClient
- [ ] `_without_none(**payload)` — strip None values from payload dict

---

## Typed Helpers

> requires: Client

All three helper mixins have signatures but raise `NotImplementedError`. Implement all as thin wrappers over `self.register(...)`, `self.get(...)`, `self.list(...)`, `self.set(...)`, `self.transition(...)`.

**`_hypothesis.py`** (Claims, Assumptions, Predictions, IndependenceGroups, PairwiseSeparations)
- [ ] `register_claim`, `get_claim`, `list_claims`, `set_claim`, `transition_claim`
- [ ] `register_assumption`, `get_assumption`, `list_assumptions`, `set_assumption`
- [ ] `register_prediction`, `get_prediction`, `list_predictions`, `set_prediction`, `transition_prediction`
- [ ] `register_independence_group`, `get_independence_group`, `list_independence_groups`, `set_independence_group`
- [ ] `register_pairwise_separation`, `get_pairwise_separation`, `list_pairwise_separations`

**`_structure.py`** (Analyses, Parameters, Datasets)
- [ ] `register_analysis`, `get_analysis`, `list_analyses`, `set_analysis`
- [ ] `register_parameter`, `get_parameter`, `list_parameters`, `set_parameter`
- [ ] `record_analysis_result(analysis_id, result, *, sha, date)` — delegate to gateway
- [ ] `register_dataset`, `get_dataset`, `list_datasets`, `set_dataset`

**`_registry.py`** (Theories, Discoveries, DeadEnds, ResearchObjectives)
- [ ] `register_theory`, `get_theory`, `list_theories`, `set_theory`, `transition_theory`
- [ ] `register_discovery`, `get_discovery`, `list_discoveries`, `set_discovery`, `transition_discovery`
- [ ] `register_dead_end`, `get_dead_end`, `list_dead_ends`, `set_dead_end`, `transition_dead_end`
- [ ] `register_research_objective`, `get_research_objective`, `list_research_objectives`, `set_research_objective`, `transition_research_objective`

---

## Views

> requires: Validate

- [ ] `run_health_check(graph, validator)` in `views/health.py` — run validator, compute overall status, return `HealthReport`

---

## Tests

> requires: Gateway, Client, Typed Helpers, Views

- [ ] Gateway: register round-trip for at least one entity (claim)
- [ ] Gateway: get / list / set / transition round-trips
- [ ] Gateway: query round-trips (claim_lineage, refutation_impact, parameter_impact)
- [ ] Gateway: CRITICAL finding blocks mutation, graph unchanged
- [ ] Gateway: dry_run returns findings without mutating
- [ ] Gateway: broken reference returns error result
- [ ] Gateway: duplicate ID returns error result
- [ ] Gateway: record_analysis_result round-trip
- [ ] Client: `connect()` returns a working client against a temp workspace
- [ ] Client: register_* / get_* / list_* helpers for all entity types
- [ ] Client: set_* helpers for all entity types
- [ ] Client: transition_* helpers for status-bearing entities
- [ ] Client: record_analysis_result round-trip through client
- [ ] Client: dry_run=True validates without writing
- [ ] Client: schema validation errors surface as ClientResult errors, not exceptions
- [ ] Health: run_health_check returns HEALTHY on a clean graph
- [ ] Health: run_health_check returns WARNING / CRITICAL on a graph with violations
- [ ] Invariants: validate_adjudicated_prediction_no_analysis fires on adjudicated prediction with no analysis
- [ ] Invariants: validate_revised_claim_downstream_impact fires on prediction/claim citing a REVISED claim
- [ ] Invariants: validate_active_theory_claims_retracted fires on ACTIVE theory with all claims retracted
- [ ] Invariants: validate_deprecated_dataset_usage fires on analysis using a DEPRECATED dataset
- [ ] Invariants: validate_research_objective_status_consistency fires on TARGETED objective with no viable theories
- [ ] Invariants: validate_abandoned_objective_active_theories fires on ABANDONED objective with ACTIVE theories
- [ ] Gateway: ResearchObjective register / get / list / set / transition round-trips
- [ ] Gateway: Dataset register / get / list / set round-trips
- [ ] Client: register_* / get_* / set_* helpers for ResearchObjective and Dataset

---

## Exit Criteria

Every item below must be true before this target is closed:

- [ ] `client = ds.connect()` works from a Python script in a real workspace directory
- [ ] All 12 entity types can be registered through typed keyword-argument helpers
- [ ] All 12 entity types can be updated through typed `set_*` helpers
- [ ] All status-bearing entities can be transitioned through typed helpers
- [ ] Analysis results can be recorded programmatically via `record_analysis_result`
- [ ] All named queries return structured `ClientResult` objects suitable for notebooks
- [ ] `run_health_check` returns a `HealthReport` with correct overall status
- [ ] Validation failures (schema errors, broken refs, CRITICAL invariants) fail fast without writing
- [ ] dry_run=True validates and returns findings without mutating the graph
- [ ] All of the above is covered by automated tests

---

## Deferred

Everything below is deferred until the exit criteria above are met:

- CLI command handlers
- MCP server and tools
- `controlplane/check.py` (staleness detection)
- `controlplane/render.py` and `controlplane/export.py`
- `controlplane/prose.py`
- `views/status.py` and `views/metrics.py`
- `adapters/markdown_renderer.py`
- Payload schema artifact files under `schemas/payloads/`
- Optimistic concurrency control
- Query performance indexing
