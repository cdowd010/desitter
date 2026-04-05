# deSitter — Tracker

Status legend: `[ ]` pending · `[~]` in progress · `[x]` done · `[-]` deferred/blocking

Purpose: this file is the current source of truth for where the repo is and the shortest path to a product that is usable through the Python API.

---

## Product Target

- Primary release gate: a researcher or agent can use deSitter from Python scripts and notebooks without hand-authoring raw JSON dicts for common workflows.
- Secondary release gate: CLI and MCP are thin delegates over the same gateway and shared read-side services.
- Explicit non-goals for the first usable product: polished CLI UX, shell completions, performance indexing, prose sync, separate result-history subsystem, or additional interface layers.

---

## Architecture Rules

These are execution rules, not just ideals. New work should be rejected if it violates them.

- All writes flow through one mutation boundary: `controlplane/gateway.py`.
- Python API is the primary interface for the first usable product; CLI and MCP come after and must stay thin.
- The client changes calling conventions only. It must not add business logic or bypass invariants.
- `EpistemicWeb` remains the kernel mutation surface. `Gateway` orchestrates persistence, validation, and logging around it.
- `controlplane/` depends on abstractions from `epistemic/ports.py`; concrete adapter wiring stays in `factory.py`.
- Payload validation stays behind the `PayloadValidator` port. Do not add inline gateway validation or interface-layer validation rules.
- Machine-readable payload schemas are allowed only if they stay aligned with `epistemic/model.py` and do not become a competing hand-maintained source of truth.
- Interface modules parse inputs, call services, and format outputs. If an interface needs logic that another interface also needs, that logic belongs lower.
- Prefer composition over inheritance. Extend the client by wrapping shared `register`, `set`, `transition`, and `query` methods instead of creating parallel mutation paths.
- Fail fast: schema errors, broken references, and invariant failures should surface before persistence.
- Keep modules high-cohesion and low-coupling. Tasks that change together should be grouped together; tasks that do not should not be forced into the same module.
- YAGNI applies. Do not add concurrency control, indexing, or a result-history model until the Python API MVP ships and proves those needs are real.

---

## Current Tracked Items

- [x] Domain kernel: entities, typed IDs, enums, invariants, copy-on-write web mutations, traversal queries, and `record_analysis_result` on `EpistemicWeb`.
- [x] Config and runtime context: `load_config`, `build_context`, `ProjectContext`.
- [x] Transaction log adapter.
- [x] JSON repository `load()` and `save()`.
- [x] JSON repository hydration: `load()` binds register methods on the current web per entity, preserving all items in a collection.
- [x] Payload validation as a port plus JSON Schema adapter, wired in the gateway factory.
- [x] Payload schema derivation models `None` explicitly as JSON `null` for `Optional[...]` fields.
- [x] Core gateway verbs: `register`, `get`, `list`, `set`, `transition`, `query`.
- [x] Base Python client with `connect()` and entity-specific `register_*`, `get_*`, `list_*`, and `transition_*` helpers.
- [x] Python client tests for round-trip registration, `connect()` wiring, and schema-error surfacing.
- [ ] Entity-specific `set_*` helpers are not present on `DeSitterClient`.
- [ ] `record_analysis_result` is not exposed through `Gateway`.
- [ ] `record_analysis_result` is not exposed through `DeSitterClient`.
- [ ] There is no checked-in `schemas/payloads/` directory with machine-readable payload schemas for external tooling.
- [ ] CLI command handlers are currently feature-gated placeholders pending milestone 3 wiring.
- [ ] MCP does not expose a `record_result` tool yet.
- [ ] `controlplane/validate.py` orchestration is still stubbed.
- [ ] `controlplane/check.py` orchestration is still stubbed.
- [ ] `controlplane/export.py` is still stubbed.
- [ ] `views/health.py`, `views/status.py`, `views/metrics.py`, and `views/render.py` are still stubbed.
- [ ] `adapters/markdown_renderer.py` surface renderers are still stubbed.
- [ ] CLI and MCP integration tests are effectively missing.

### Audit-Driven Hardening (Scoped)

- [x] Regression tests proving repository hydration preserves multiple entities per collection and accumulates state across collection boundaries.
- [x] Payload-validator tests proving `Optional[str]` rejects object payloads and accepts explicit `null`.
- [x] Feature-gated CLI/MCP commands backed by stubbed read-side services.
- [ ] Keep tightening fail-fast type boundaries around `Any`-typed model fields while preserving Python API MVP scope.
- [ ] Decide post-MVP persistence policy for non-JSON-native values (avoid silent `default=str` coercion unless explicitly intended).
- [ ] Scope a per-call query index-reuse pass in `EpistemicWeb` (`assumption_support_status`, `parameter_impact`) after Milestone 1 API gates close, without introducing global caches.
- [ ] Introduce a `JSONValue` alias and migrate persisted payload-bearing fields away from broad `Any` types in a staged pass.
- [ ] Remove repository `json.dumps(..., default=str)` once `JSONValue` boundaries are enforced and migration tests are in place.

### Known Drift to Resolve

- [ ] Old tracker content understated current Python API progress and overstated some gaps.
- [ ] Architecture docs and examples still drift on the result-recording story; current kernel model is `Analysis.last_result`, `last_result_sha`, and `last_result_date`.
- [ ] Docs/examples still mix `transaction_id` and `tx_id` terminology.

---

## Milestone 1 — Python API MVP `[~]`

Goal: produce a Python-first workflow that is genuinely usable in scripts, notebooks, and by non-MCP agents.

### 1A. Core API Ergonomics

- [x] `connect()` with optional path returns a ready client.
- [x] Entity-specific `register_*` helpers exist.
- [x] Entity-specific `get_*`, `list_*`, and `transition_*` helpers exist.
- [ ] Add entity-specific `set_*` helpers in `src/desitter/client.py` for:
  claim, assumption, prediction, analysis, theory, discovery, dead_end, parameter, independence_group, pairwise_separation.
- [ ] Implement those helpers as thin wrappers over the shared `client.set(...)` path.
- [ ] Keep helper payload assembly DRY: shared conversion helpers stay in shared code, not duplicated per interface.

### 1B. Analysis Result Workflow

- [x] Kernel mutation already exists: `EpistemicWeb.record_analysis_result(...)`.
- [ ] Add `Gateway.record_analysis_result(...)` in `src/desitter/controlplane/gateway.py` as a narrow wrapper over the kernel mutation.
- [ ] Add `DeSitterClient.record_analysis_result(...)` in `src/desitter/client.py`.
- [ ] Decide and document one stable calling convention for programmatic result recording.
- [ ] Do not add a second write path or a separate result subsystem for this milestone.

### 1C. Formalize Payload Schemas

- [ ] Add checked-in JSON Schema files under `schemas/payloads/`, one per gateway resource payload.
- [ ] Cover at least: `claim`, `assumption`, `prediction`, `analysis`, `theory`, `discovery`, `dead_end`, `parameter`, `independence_group`, and `pairwise_separation`.
- [ ] Make required vs optional fields match the kernel dataclasses in `src/desitter/epistemic/model.py`.
- [ ] Keep the model definitions authoritative. Schema files are generated artifacts, not hand-maintained sources of truth.
- [ ] Extract schema derivation into one pure shared module, so runtime validation and checked-in artifacts both come from the same builder.
- [ ] Move the current schema-building logic out of `src/desitter/adapters/payload_validator.py` into a reusable pure module under `src/desitter/epistemic/`.
- [ ] Have `JsonSchemaPayloadValidator` build its validators from that shared schema map rather than owning a private derivation path.
- [ ] Add one deterministic regeneration entry point that writes `schemas/payloads/*.schema.json` in stable resource order with sorted keys.
- [ ] Treat `schemas/payloads/` as committed external-tooling artifacts. Never edit those files by hand.
- [ ] Keep validation usage behind `PayloadValidator`; do not add inline validation branches to `Gateway`.
- [ ] Add tests that fail when checked-in schemas drift from the effective payload validator rules.

### 1D. Python API Verification

- [ ] Expand `tests/test_client.py` to cover the new `set_*` helpers.
- [ ] Add tests for `record_analysis_result` round-trip through gateway, repository, and transaction log.
- [ ] Add tests for dry-run behavior on update and result-recording paths.
- [ ] Add tests for schema artifact presence and compatibility with the payload validator.
- [ ] Add one Python-first usage example once the API shape stabilizes.

### Milestone 1 Exit Criteria

- [ ] A user can `connect()` from Python.
- [ ] A user can register common entities through typed helpers.
- [ ] A user can update existing entities through typed `set_*` helpers.
- [ ] A user can record an analysis result programmatically.
- [ ] External tooling can consume machine-readable payload schemas that match gateway validation behavior.
- [ ] Reads (`get`, `list`, `query`) return typed objects or structured data appropriate for scripts and notebooks.
- [ ] Validation failures fail fast and do not write.
- [ ] The Python API path is covered by automated tests.

---

## Milestone 2 — Shared Read-Side Services `[ ]`

Goal: implement the read/report/render/export layer that both CLI and MCP need, without pushing logic upward into interfaces.

- [ ] Implement `validate_project` and `validate_structure` in `src/desitter/controlplane/validate.py`.
- [ ] Implement `compute_metrics` and `tier_a_evidence_summary` in `src/desitter/views/metrics.py`.
- [ ] Implement `get_status` and `format_status_dict` in `src/desitter/views/status.py`.
- [ ] Implement `run_health_check` in `src/desitter/views/health.py`.
- [ ] Implement `check_refs` and `check_stale` in `src/desitter/controlplane/check.py`.
- [ ] Implement render fingerprinting and cache orchestration in `src/desitter/views/render.py`.
- [ ] Implement markdown surface rendering in `src/desitter/adapters/markdown_renderer.py`.
- [ ] Implement `export_json` and `export_markdown` in `src/desitter/controlplane/export.py`.
- [ ] Add focused tests for each read-side service instead of relying on interface smoke tests alone.

### Milestone 2 Exit Criteria

- [ ] The project can validate itself through shared services.
- [ ] The project can compute status/metrics/health from shared services.
- [ ] The project can render and export through shared services.
- [ ] CLI and MCP can consume these services without adding business logic.

---

## Milestone 3 — CLI and MCP Backfill `[ ]`

Goal: make CLI and MCP thin, working delegates over the already-implemented gateway and read-side services.

### 3A. CLI

- [ ] Wire CLI `register`, `get`, `list`, `set`, and `transition` to the gateway in `src/desitter/interfaces/cli/main.py`.
- [ ] Add CLI `record` command for analysis result recording.
- [ ] Wire CLI `validate`, `health`, `status`, `render`, `export`, and `init` to shared services only.
- [ ] Keep `src/desitter/interfaces/cli/formatters.py` formatting-only.
- [ ] Add CLI tests via `click.testing.CliRunner`.

### 3B. MCP

- [ ] Add `record_result` tool in `src/desitter/interfaces/mcp/tools.py`.
- [ ] Keep all MCP handlers status-first and envelope-only.
- [ ] Do not let MCP handlers reach through private collaborators or duplicate gateway logic.
- [ ] Add MCP handler tests against fake or minimal gateways/services.

### Milestone 3 Exit Criteria

- [ ] CLI and MCP expose the same semantics as the Python API and gateway.
- [ ] Interface adapters contain parsing/formatting only.
- [ ] There is no second business-logic path outside the gateway and shared read services.

---

## Milestone 4 — Documentation and Coherence `[ ]`

Goal: align the repo’s planning docs and onboarding docs with the code that actually exists.

- [ ] Keep this tracker current after each milestone closes.
- [ ] Update `ARCHITECTURE.md` status tables and implementation notes to match the repo.
- [ ] Update `README.md` to lead with the Python API workflow.
- [ ] Add one script example and one notebook-style example.
- [ ] Document where payload schemas live, how they are produced, and how external tools should consume them.
- [ ] Align terminology: `transaction_id`, result-recording model, `desitter.toml` as config source of truth.
- [ ] Remove stale roadmap references to a separate result-history subsystem unless it becomes necessary later.

---

## Deferred Until After Python API MVP `[-]`

- [ ] Separate result-history or event-sourcing model.
- [ ] Optimistic concurrency control or locking.
- [ ] Prose sync adapter.
- [ ] Query-performance indexing and benchmark suite.
- [ ] Rich interactive CLI UX, completions, dashboards, and shell ergonomics.
- [ ] Additional interface layers such as REST.

---

## Suggested Execution Order

1. Add `Gateway.record_analysis_result(...)`.
2. Add `DeSitterClient.record_analysis_result(...)`.
3. Add all client `set_*` helpers.
4. Formalize checked-in payload schemas behind the existing `PayloadValidator` path.
5. Expand Python API tests until the script/notebook flow is solid.
6. Implement shared read-side services.
7. Backfill CLI and MCP to delegate to those services.
8. Align docs to the shipped behavior.

---

## Definition of “Usable by Python API”

- [ ] `client = desitter.connect()` works in a real project workspace.
- [ ] Common entities can be registered through typed helpers.
- [ ] Common entities can be updated through typed `set_*` helpers.
- [ ] Analysis results can be recorded from Python.
- [ ] External tools can discover payload shapes from checked-in schemas without reverse-engineering examples.
- [ ] Queries and lookups return typed or structured results suitable for notebooks.
- [ ] Dry-run and validation failures fail fast and do not write.
- [ ] The above workflow is covered by automated tests and documented in one clear example.