# deSitter — Project Tracker

Status legend: `[ ]` pending · `[~]` in progress · `[x]` done · `[-]` blocked

---

## Phase 1 — Domain Core
> Goal: fully tested epistemic kernel. Zero I/O. Pure Python.

- [x] `epistemic/types.py` — typed IDs, enums, Finding (`TheoryId`, `AnalysisId`, `DeadEndId`, `DeadEndStatus`)
- [x] `epistemic/model.py` — 11 entity dataclasses: `Claim`, `Assumption`, `Prediction`, `Theory`, `Discovery`, `Analysis`, `IndependenceGroup`, `PairwiseSeparation`, `DeadEnd`, `Concept`, `Parameter`; `source` field on all research content entities; `Analysis.uses_parameters` + `Parameter.used_in_analyses` for staleness detection
- [x] `epistemic/web.py` — EpistemicWeb aggregate root; bidirectional maintenance for all 5 link pairs
- [x] `epistemic/invariants.py` — tier, independence semantics, coverage, assumption testability validators
- [x] `epistemic/ports.py` — `WebRepository`, `WebRenderer`, `WebValidator`, `ProseSync`, `TransactionLog` protocols
- [ ] Tests: entity construction and field defaults, including `source`, `uses_parameters`, `used_in_analyses` (~12 tests)
- [ ] Tests: register happy path for all entity types (~11 tests)
- [ ] Tests: duplicate ID, broken reference, cycle detection (~15 tests)
- [ ] Tests: bidirectional link maintenance — all 5 pairs (~12 tests)
- [ ] Tests: claim_lineage, assumption_lineage on multi-level graphs (~8 tests)
- [ ] Tests: all invariant validators with known violations (~18 tests)

**Exit criteria:** ~76 tests passing. No external deps. Runs in milliseconds.

---

## Phase 2 — Persistence and Packaging
> Goal: JSON adapter, context builder, installable package.

- [ ] `adapters/json_repository.py` — load/save EpistemicWeb as JSON files; round-trip includes `source`, `uses_parameters`, `used_in_analyses`
- [ ] `adapters/transaction_log.py` — JSONL provenance log (append/read)
- [ ] `adapters/markdown_renderer.py` — claims, predictions, assumptions, theories, analyses summary views; renders `doi:` and `arxiv:` sources as links
- [ ] `config.py` — `load_config` + `build_context`; `desitter.toml` parsing; already implemented as stub
- [ ] `pyproject.toml` — verify `pip install -e .` works
- [ ] `desitter/__init__.py` — re-export common public API entry points
- [ ] Tests: round-trip load/save for all entity types including new fields
- [ ] Tests: context path derivation from workspace root

**Exit criteria:** `pip install -e .` works. Full round-trip through JSON for every entity type.

---

## Phase 3 — Core and View Services
> Goal: single mutation boundary + view services wired to JSON repo.

- [ ] `controlplane/gateway.py` — register, get, list, set, transition, query; validate-after-write; rollback on failure; dry-run
- [ ] `controlplane/validate.py` — validate_project, validate_structure
- [ ] `controlplane/check.py` — check_refs, check_stale (uses `Analysis.uses_parameters` ↔ `Parameter.used_in_analyses`)
- [ ] `controlplane/export.py` — export_json, export_markdown
- [ ] `controlplane/automation.py` — render trigger table wired into gateway
- [ ] `views/render.py` — SHA-256 fingerprint cache + incremental render
- [ ] `views/health.py` — run_health_check; structural findings + broken `source` references
- [ ] `views/status.py` — get_status, format_status_dict
- [ ] `views/metrics.py` — compute_metrics, tier_a_evidence_summary
- [ ] Tests: gateway register → validate-after-write → rollback on violation
- [ ] Tests: dry-run semantics
- [ ] Tests: resource alias resolution
- [ ] Tests: `check_stale` identifies correct stale analyses after parameter change
- [ ] Tests: `validate_assumption_testability` surfaces assumptions with falsifiable_consequence but no tested_by predictions

**Exit criteria:** Gateway fully tested through InMemoryRepository. View services return correct output on fixture data.

---

## Phase 4 — Interface Layer (CLI + MCP)
> Goal: two thin interface adapters over the same core. Ships the MCP server.

### CLI (`interfaces/cli/`)
- [ ] `interfaces/cli/main.py` — commands: `register`, `get`, `list`, `set`, `transition`, `validate`, `health`, `status`, `render`, `export`, `init`
- [ ] `interfaces/cli/formatters.py` — Rich tables + JSON fallback; `doi:` and `arxiv:` sources rendered as clickable links
- [ ] `__main__.py` — `python -m desitter` works
- [ ] `ds init` — creates `project_config.json`, standard directory layout; idempotent

### MCP Server (`interfaces/mcp/`)
- [ ] `interfaces/mcp/server.py` — FastMCP server, tool registration
- [ ] `interfaces/mcp/tools.py` — tool handlers: `register_resource`, `get_resource`, `list_resources`, `set_resource`, `transition_resource`, `query_web`, `validate_web`, `health_check`, `project_status`, `render_views`, `check_stale`, `check_refs`, `export_web`

### Tests
- [ ] Tests: core CLI commands via CliRunner
- [ ] Tests: MCP tool handlers with gateway fakes
- [ ] Tests: `ds init` creates correct directory layout

**Exit criteria:** An AI agent can register, validate, health-check, and export through MCP. A human can do the same through the CLI.

---

## Phase 5 — Human-First UX
> Goal: the web becomes navigable. Researcher can traverse and audit without writing JSON.

- [ ] Rich progress bars for long-running operations
- [ ] `ds status` dashboard (color-coded, summary panels)
- [ ] `ds validate --fix` dry-run suggestions
- [ ] Consistent error messages with actionable hints
- [ ] `ds add <type>` — interactive prompts for all core entity types; prompts for `source`, `derivation`
- [ ] `ds show <type> [id]` — human-readable view with relationships; `source` rendered as link
- [ ] `ds log [id]` — mutation history from transaction log
- [ ] Shell completions (bash, zsh, fish) with resource ID tab-completion
- [ ] `ds config set|get` — read/write `project_config.json` without editing JSON directly
- [ ] Quickstart guide: install → init → add theory → add claim → add prediction → record result → render

**Exit criteria:** A researcher unfamiliar with the project can install, init, add a claim, and render views without consulting source code.

---

## Phase 6 — Results Ingestion
> Goal: deSitter consumes results from researcher-run analyses. No execution, no sandboxing.

- [ ] `adapters/results_repository.py` — load/save `AnalysisResult` list from `data/results.json`; multiple results per analysis in insertion order
- [ ] `controlplane/results.py` — `record_result(context, analysis_id, prediction_id, value, uncertainty, status, notes, dry_run)`; persists to `data/results.json`; transitions prediction status; appends to transaction log
- [ ] `ds record <analysis_id>` CLI command — `--value`, `--uncertainty`, `--status`, `--notes`, `--no-transition`, `--json`
- [ ] `record_result` MCP tool — returns standard `GatewayResult` envelope
- [ ] `desitter.record()` SDK shim — one-line instrumentation for any Python script
- [ ] Git SHA auto-capture in `ds record` — calls `git rev-parse HEAD`; warns if `Analysis.path` file has uncommitted changes at record time
- [ ] `controlplane/export.py` — export includes recorded results with uncertainty and git_sha
- [ ] `ds results <analysis_id>` — show result history; displays value, uncertainty, status, git_sha, source, timestamp
- [ ] Tests: `record_result` persists to `data/results.json` and transitions prediction status correctly
- [ ] Tests: `--no-transition` suppresses status change
- [ ] Tests: uncertainty round-trips through JSON
- [ ] Tests: git SHA captured when in git repo; warning emitted when analysis file has uncommitted changes
- [ ] Tests: `parameter_snapshot` captures values of all `Analysis.uses_parameters` at record time
- [ ] Tests: SDK shim delegates to same gateway endpoint as CLI

**Exit criteria:** A researcher can record a result from a script with one line. An agent can record it with one MCP tool call.

---

## Architecture Remediation Backlog (Cross-Phase)
> Goal: fix boundary architecture issues immediately, and track intentionally unimplemented modules without ad hoc implementation.

- [x] Fix MCP boundary contract mismatches (`render_all` call shape, `check_refs` args)
- [x] Remove MCP private reach-through into gateway internals (`gateway._repo`, `gateway._validator`) by adding public read-only accessors
- [ ] Add architecture contract test: no private gateway collaborator access from interface adapters
- [ ] Add architecture contract test: MCP wrapper signatures match underlying service function signatures
- [ ] Add architecture contract test: status-first envelope is stable for all MCP tools
- [ ] Document and enforce policy: stubs are only implemented in their owning phase below

### Top 5 PR Milestones

- [ ] PR-A1: Boundary contract hardening and adapter encapsulation guardrails
- [ ] PR-B1: Gateway mutation orchestration (`register`) with validate-after-write + dry-run + tx log
- [ ] PR-B2: Gateway read/query routes (`get`, `list`, `query`) and canonical payload normalization
- [ ] PR-C1: Adapter completeness (`JsonRepository`, `MarkdownRenderer`) with round-trip tests
- [ ] PR-D1: Read-service completeness (`validate`, `check`, `render`, `status`, `metrics`, `health`, `export`) and shared fixtures

---

## Boundary Test Matrix Execution Backlog
> Goal: close CLI/MCP/gateway/render/check/status blind spots in the fastest order.

- [ ] P0 CLI -> Gateway delegation tests (`register`, `get`, `list`, `set`, `transition`)
- [ ] P0 MCP -> Gateway wrapper tests with fake gateway and deterministic envelopes
- [ ] P0 MCP -> service boundary tests for `render_views`, `check_refs`, `health_check`, `project_status`
- [ ] P0 Gateway transaction tests: rollback on CRITICAL, dry-run no-save, tx logging on writes
- [ ] P1 Render cache tests: unchanged fingerprint skip, changed fingerprint write, cache persist/load
- [ ] P1 Check service tests: stale analysis and broken reference findings on synthetic mini-web fixtures
- [ ] P1 Status/metrics/health read-model tests with fixed fixture snapshots
- [ ] P2 CLI/MCP parity tests: same operation, equivalent semantic result

---

## Query Performance Strategy Backlog
> Goal: keep current behavior unchanged while adding internal indexes for larger graph workloads.

- [ ] Add `implicit_assumption_to_predictions` query index (used by `assumption_support_status`, `validate_implicit_assumption_coverage`)
- [ ] Add `claim_to_downstream_claims` reverse-closure index (used by claim/prediction blast-radius queries)
- [ ] Add `analysis_to_predictions` index for direct analysis-linked prediction impact
- [ ] Add `parameter_to_constrained_claims` index for parameter threshold blast radius
- [ ] Add lazy-build + invalidation strategy per `EpistemicWeb` instance
- [ ] Add benchmark suite for small/medium/large synthetic graphs and set acceptance thresholds
- [ ] Roll out indexes behind a feature flag until benchmark thresholds are stable
