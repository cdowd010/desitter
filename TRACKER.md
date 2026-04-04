# deSitter — Project Tracker

Status legend: `[ ]` pending · `[~]` in progress · `[x]` done · `[-]` blocked

Last updated: 2026-04-04 · 337 tests passing

---

## Phase 1 — Domain Core ✓
> Goal: fully tested epistemic kernel. Zero I/O. Pure Python.

- [x] `epistemic/types.py` — typed IDs, enums (`ClaimId`, `AssumptionId`, `PredictionId`, `AnalysisId`, `TheoryId`, `IndependenceGroupId`, `PairwiseSeparationId`, `DiscoveryId`, `DeadEndId`, `ParameterId`); `ConfidenceTier`, `DeadEndStatus`, `DiscoveryStatus`, `ClaimStatus`, `AssumptionType`, `ClaimType`, `ClaimCategory`
- [x] `epistemic/model.py` — 10 entity dataclasses: `Claim`, `Assumption`, `Prediction`, `Theory`, `Discovery`, `Analysis`, `IndependenceGroup`, `PairwiseSeparation`, `DeadEnd`, `Parameter`; `source` field on all research content entities; `Analysis.uses_parameters` + `Parameter.used_in_analyses` for staleness detection
- [x] `epistemic/web.py` — `EpistemicWeb` aggregate root; copy-on-write mutation semantics; bidirectional maintenance for all 5 link pairs; all `register_*`, `update_*`, `remove_*`, `transition_*`, `add_*` methods; full traversal query surface (`claim_lineage`, `assumption_lineage`, `refutation_impact`, `parameter_impact`, etc.)
- [x] `epistemic/invariants.py` — tier, independence semantics, coverage, assumption testability validators
- [x] `epistemic/ports.py` — `WebRepository`, `WebRenderer`, `WebValidator`, `ProseSync`, `TransactionLog` protocols
- [x] Tests: entity construction and field defaults (19 tests · `test_model.py`)
- [x] Tests: types and enums (20 tests · `test_types.py`)
- [x] Tests: ports protocol conformance (5 tests · `test_ports.py`)
- [x] Tests: register — happy path + duplicate ID + broken reference for all entity types (58 tests · `test_web_register.py`)
- [x] Tests: update — happy path + nonexistent + broken reference (45 tests · `test_web_update.py`)
- [x] Tests: remove — blocking refs and backlink teardown (47 tests · `test_web_remove.py`)
- [x] Tests: transitions — all valid/invalid status arcs (16 tests · `test_web_transitions.py`)
- [x] Tests: queries — `claim_lineage`, `assumption_lineage`, `refutation_impact`, `parameter_impact`, etc. (37 tests · `test_web_queries.py`)
- [x] Tests: immutability — mutations return new web, caller isolation (8 tests · `test_web_immutability.py`)
- [x] Tests: backlink ownership — backlinks stored on correct side of every link pair (3 tests · `test_web_backlink_ownership.py`)
- [x] Tests: all invariant validators with known violations (31 tests · `test_invariants.py`)

**Exit criteria met:** 294 kernel tests passing. No external deps. Runs in milliseconds.

---

## Phase 2 — Persistence and Packaging
> Goal: JSON adapter, transaction log, config wiring, installable package.

- [x] `adapters/transaction_log.py` — JSONL provenance log (append/read); tested (8 tests · `test_transaction_log.py`)
- [x] `config.py` — `load_config` + `build_context`; `desitter.toml` parsing; tested (9 tests · `test_config.py`)
- [x] `controlplane/automation.py` — render trigger table; `DEFAULT_RENDER_TRIGGERS`; tested (7 tests · `test_automation.py`)
- [x] `pyproject.toml` — `pip install -e .` works; `desitter` + `desitter[mcp]` extras
- [ ] `adapters/json_repository.py` — implement `load()`/`save()` (both currently `raise NotImplementedError`); round-trip all 10 entity types including `source`, `uses_parameters`, `used_in_analyses`
- [ ] `adapters/markdown_renderer.py` — implement `render_claims`, `render_predictions`, `render_assumptions`, `render_theories` (all currently `raise NotImplementedError`); render `doi:` and `arxiv:` sources as links
- [ ] Tests: round-trip load/save for all 10 entity types including new fields (target: ~12 tests)
- [ ] Tests: markdown renderer output for each entity type (target: ~8 tests)

**Exit criteria:** `pip install -e .` works. Full round-trip through JSON for every entity type. Markdown renders clean output.

---

## Phase 3 — Control Plane and View Services
> Goal: single mutation boundary fully implemented; all view services operational.

### Gateway (`controlplane/gateway.py`)
The `Gateway` class and all constants/aliases/boilerplate exist. The 6 core operation methods are stubbed:

- [ ] `register(resource, payload, *, dry_run)` — parse payload → construct entity → call `web.register_*` → validate-after-write → rollback on CRITICAL → log transaction → save
- [ ] `get(resource, identifier)` — resolve alias → load web → look up entity → serialize to dict
- [ ] `list(resource, **filters)` — resolve alias → load web → return all entities of type, filtered
- [ ] `set(resource, identifier, payload, *, dry_run)` — load → deep-copy entity → apply payload fields → call `web.update_*` → validate-after-write → rollback → log → save
- [ ] `transition(resource, identifier, new_status, *, dry_run)` — load → call `web.transition_*` → validate-after-write → rollback → log → save
- [ ] `query(query_type, **params)` — load web → dispatch to `web.<query_method>(**params)` → serialize result
- [ ] Tests: `register` → validate-after-write → rollback on violation (~6 tests · `test_gateway.py`)
- [ ] Tests: `dry_run` — validate but do not write (~3 tests)
- [ ] Tests: resource alias resolution covers all canonical + plural + hyphenated forms (~4 tests)
- [ ] Tests: `get` / `list` return correct serialized payloads (~6 tests)
- [ ] Tests: `set` / `transition` mutate and persist correctly (~6 tests)

### Check and Export (`controlplane/check.py`, `controlplane/export.py`)
All functions currently `raise NotImplementedError`:

- [ ] `check_refs(context)` — load web; walk all ID references; report broken links
- [ ] `check_stale(context)` — identify analyses whose `uses_parameters` have changed since last result; report stale prediction chain
- [ ] `check_missing_results(context)` — analyses with predictions that have no recorded result
- [ ] `check_assumption_coverage(context)` — assumptions with `falsifiable_consequence` but no `tested_by` predictions
- [ ] `export_json(context, dest)` — write full web as JSON bundle to `dest`
- [ ] `export_markdown(context, dest)` — write rendered markdown views to `dest`
- [ ] Tests: `check_stale` identifies correct stale analyses after parameter change (~3 tests)
- [ ] Tests: `check_refs` surfaces broken references on synthetic fixture (~3 tests)

### Validate (`controlplane/validate.py`)
- [ ] Flesh out `validate_project` + `validate_structure` beyond current 2-test stub
- [ ] Tests: surfaces invalid web state with human-readable findings (~5 tests)

### View Services (`views/`)
All view functions currently `raise NotImplementedError`:

- [ ] `views/health.py` — `run_health_check` → compose findings from check + validate + refs; return `HealthReport(status="HEALTHY"|"WARNINGS"|"CRITICAL", findings=[...])`
- [ ] `views/render.py` — SHA-256 fingerprint cache; `render_all`, `render_one`, `load_cache`, `save_cache` (incremental — skip unchanged entities)
- [ ] `views/status.py` — `get_status` → entity counts, phase, last-mutation timestamp; `format_status_dict`
- [ ] `views/metrics.py` — `compute_metrics` → tier-A evidence ratio, assumption coverage rate, stale-analysis count; `tier_a_evidence_summary`
- [ ] Tests: `run_health_check` returns correct severity on fixture data (~4 tests)
- [ ] Tests: render cache — unchanged fingerprint skip, changed fingerprint write (~4 tests)
- [ ] Tests: `get_status` / `compute_metrics` return correct values on fixture web (~4 tests)

**Exit criteria:** Gateway fully tested through `InMemoryRepository`. All view services return correct output on fixture data.

---

## Phase 4 — Interface Layer (CLI + MCP)
> Goal: two thin interface adapters over the same core. Ships the MCP server.

### CLI (`interfaces/cli/`)
The Click command group and command stubs exist in `cli/main.py` (11 handlers raise `NotImplementedError`). `formatters.py` and `__main__.py` exist.

- [ ] `register` command — route to `gateway.register`; accept JSON string or `--field=value` flags
- [ ] `get` command — route to `gateway.get`; `--json` flag for machine output
- [ ] `list` command — route to `gateway.list`; tabular + JSON output
- [ ] `set` command — route to `gateway.set`; `--dry-run` flag
- [ ] `transition` command — route to `gateway.transition`; `--dry-run` flag
- [ ] `validate` command — route to `validate_project`; `--json` flag
- [ ] `health` command — route to `run_health_check`; exit code 1 on CRITICAL
- [ ] `status` command — route to `get_status`; summary panel via Rich
- [ ] `render` command — route to `render_all`; progress bar on large webs
- [ ] `export` command — route to `export_json` / `export_markdown`; `--format` flag
- [ ] `init` command — create `project_config.json` and standard directory layout; idempotent
- [ ] Tests: core CLI commands via CliRunner (~15 tests · `tests/cli/`)

### MCP Server (`interfaces/mcp/`)
`tools.py` wrappers exist and delegate correctly. The underlying services they call (gateway + views) are the stubs above.

- [ ] `interfaces/mcp/server.py` — wire `register_tools(server, context)` with correct context loading + FastMCP startup
- [ ] `ds-mcp` entry point works end-to-end once gateway is implemented
- [ ] Tests: MCP tool handlers against fake gateway return correct envelopes (~10 tests · `tests/mcp/`)
- [ ] Tests: `ds init` creates correct directory layout (~2 tests)

**Exit criteria:** An AI agent can register, validate, health-check, and export through MCP. A human can do the same through the CLI.

---

## Phase 5 — Human-First UX
> Goal: the web becomes navigable. Researcher can traverse and audit without writing JSON.

- [ ] `ds status` dashboard — color-coded Rich panels; entity counts, health color, last mutation
- [ ] `ds validate --fix` dry-run suggestions printed as hints
- [ ] Consistent error messages with actionable hints (missing required field, broken reference, etc.)
- [ ] `ds add <type>` — interactive prompts for all core entity types; prompts for `source`, `derivation`
- [ ] `ds show <type> [id]` — human-readable view with relationships; `source` rendered as clickable link
- [ ] `ds log [id]` — mutation history from transaction log, formatted as table
- [ ] Shell completions (bash, zsh, fish) with resource-ID tab-completion
- [ ] `ds config set|get` — read/write `project_config.json` without editing JSON directly
- [ ] Quickstart guide: install → init → add theory → add claim → add prediction → record result → render

**Exit criteria:** A researcher unfamiliar with the project can install, init, add a claim, and render views without consulting source code.

---

## Phase 6 — Results Ingestion
> Goal: deSitter consumes results from researcher-run analyses. No execution, no sandboxing.

- [ ] `epistemic/model.py` — add `AnalysisResult` dataclass: `analysis_id`, `prediction_id`, `value`, `uncertainty`, `status`, `notes`, `git_sha`, `timestamp`, `parameter_snapshot`
- [ ] `adapters/results_repository.py` — load/save `AnalysisResult` list from `data/results.json`; multiple results per analysis in insertion order
- [ ] `controlplane/results.py` — `record_result(context, analysis_id, prediction_id, value, uncertainty, status, notes, dry_run)`; persists to `data/results.json`; transitions prediction status; appends to transaction log; captures `parameter_snapshot` at record time
- [ ] `ds record <analysis_id>` CLI — `--value`, `--uncertainty`, `--status`, `--notes`, `--no-transition`, `--json`
- [ ] `record_result` MCP tool — returns standard `GatewayResult` envelope
- [ ] `desitter.record()` SDK shim — one-line instrumentation for any Python script
- [ ] Git SHA auto-capture — calls `git rev-parse HEAD`; warns if `Analysis.path` file has uncommitted changes
- [ ] `ds results <analysis_id>` — show result history; value, uncertainty, status, git_sha, source, timestamp
- [ ] Tests: `record_result` persists and transitions prediction status correctly (~5 tests)
- [ ] Tests: `--no-transition` suppresses status change (~2 tests)
- [ ] Tests: `parameter_snapshot` captures correct values at record time (~2 tests)
- [ ] Tests: git SHA captured in repo; warning on uncommitted changes (~2 tests)
- [ ] Tests: SDK shim delegates to same gateway endpoint as CLI (~2 tests)

**Exit criteria:** A researcher can record a result from a script with one line. An agent can record it with one MCP tool call.

---

## Architecture Guardrail Backlog
> Integrity checks to add before Phase 4 ships. One-time cost, prevents regressions.

- [x] Fix MCP boundary contract mismatches (`render_all` call shape, `check_refs` args)
- [x] Remove MCP private reach-through into gateway internals (`gateway._repo`, `gateway._validator`)
- [ ] Architecture contract test: no private gateway collaborator access from interface adapters
- [ ] Architecture contract test: MCP wrapper signatures match underlying service signatures
- [ ] Architecture contract test: status-first envelope present on all MCP tools

---

## Query Performance Backlog
> Deferred until Phase 3 is stable. Do not implement speculatively.

- [ ] `implicit_assumption_to_predictions` reverse index (used by `assumption_support_status`, `validate_implicit_assumption_coverage`)
- [ ] `claim_to_downstream_claims` reverse-closure index (blast-radius queries)
- [ ] `analysis_to_predictions` index for direct analysis-linked prediction impact
- [ ] `parameter_to_constrained_claims` index for parameter threshold blast radius
- [ ] Lazy-build + per-instance invalidation strategy
- [ ] Benchmark suite for small/medium/large synthetic graphs with acceptance thresholds

