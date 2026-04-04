# deSitter

*Versioned, invariant-enforced tracking for the epistemic structure of research.*

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![License: Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Status: Early Development](https://img.shields.io/badge/status-early%20development-orange.svg)](TRACKER.md)

> **Early development — not ready for production use.**
> The API, file formats, and CLI surface are unstable. See [TRACKER.md](TRACKER.md) for current build status.

---

## What It Is

The scientific method has a structure: you make **claims**, ground them in **assumptions**, derive **predictions**, run **analyses** to test those predictions, and record what the evidence shows. That structure exists in every research project, but it almost never gets tracked. It lives in Notion pages, email threads, and researcher memory — and it breaks silently.

A refuted prediction doesn't update the claims that depend on it. A revised assumption doesn't propagate to its consequences. Six months later, nobody can trace why a conclusion was drawn or whether the underlying support was ever intact.

deSitter makes that structure explicit and machine-enforceable. It is a versioned, graph-structured registry of your **epistemic chain** — every claim, assumption, prediction, analysis, and theory — with hard invariants that keep the graph consistent as research evolves.

deSitter is an **audit scaffold**, not a reasoning engine. It surfaces structural facts about the graph: missing links, untested assumptions, stale analyses, uncovered predictions. The researcher — or an AI agent — is the one who decides what to do about them.

---

## Core Capabilities

- **Register** claims, assumptions, predictions, analyses, theories, and parameters in a typed, versioned graph
- **Enforce** referential integrity, DAG acyclicity, bidirectional links, and tier constraints at write time — not after the fact
- **Validate** the full epistemic web on demand against ten domain invariants
- **Track evidence** through prediction tiers (`FULLY_SPECIFIED`, `CONDITIONAL`, `FIT_CHECK`) with explicit independence-group accounting
- **Detect staleness** when a parameter changes and propagates to analyses and predictions
- **Health-check** the entire project in one command, with a machine-readable `HEALTHY / WARNINGS / CRITICAL` result suitable for CI
- **Render** human-readable markdown views of the project graph, incrementally

deSitter never executes analyses. Researchers run their own tools — Python, R, SageMath, Jupyter — and record outcomes. deSitter records provenance, enforces structure, and tracks what changed.

---

## Interfaces

deSitter exposes the same capabilities through two equal interfaces:

**CLI — for humans and scripts**

```bash
ds register claim '{"id": "C-001", "statement": "...", "type": "foundational", ...}'
ds health
ds validate
ds status
ds render
```

Every command accepts `--json` for machine-readable output. Shell scripts, CI pipelines, and Makefiles work naturally against the CLI.

**MCP server — for AI agents**

```bash
ds-mcp   # start the MCP server
```

The [Model Context Protocol](https://modelcontextprotocol.io) lets AI assistants (Claude, Copilot, Cursor, and others) call deSitter tools directly as structured operations — no subprocess, no parsing, no screen-scraping. An agent calls `register_claim`, `health_check`, or `query_web` with typed arguments and receives a structured response. The same gateway that serves the CLI serves the MCP server: there is no divergence in behaviour.

The MCP interface is designed with AI-assisted research in mind. An agent with access to the deSitter tool surface can audit a derivation chain, identify structural gaps, pre-flight a new prediction with `dry_run=True`, and commit it — all within a single session. The epistemic web provides the shared, persistent, invariant-enforced state. The AI provides the reasoning.

---

## Quick Start

```bash
pip install desitter            # CLI + core
pip install "desitter[mcp]"     # + MCP server for AI agent use
```

```bash
# Initialise a project workspace
ds init

# Register a claim
ds register claim '{"id": "C-001", "statement": "...", "type": "foundational", ...}'

# Run all health checks
ds health

# Check structural gaps
ds validate

# Start the MCP server
ds-mcp
```

---

## Architecture

deSitter is built in layers, from the inside out. The innermost layer — the **epistemic kernel** — is pure Python with no I/O dependencies. It defines the entity model, the `EpistemicWeb` aggregate root, and all invariant rules. Nothing in the kernel touches a file, a database, or a network socket. This is what makes the core fully testable in memory and reusable without any infrastructure.

The layers above the kernel — adapters, control plane, view services, interfaces — each have a single responsibility and depend only on layers below them.

```
┌──────────────────────────────────────────────────────┐
│  Interface Layer                                     │
│  cli/ — humans & scripts    mcp/ — AI agents         │
└─────────────────────┬────────────────────────────────┘
                      │
┌─────────────────────▼────────────────────────────────┐
│  View Services                                       │
│  health · status · metrics · render                  │
└─────────────────────┬────────────────────────────────┘
                      │
┌─────────────────────▼────────────────────────────────┐
│  Control Plane (single gateway for all mutations)    │
│  gateway · validate · check · export · automation    │
└─────────────────────┬────────────────────────────────┘
                      │
┌─────────────────────▼────────────────────────────────┐
│  Adapters                                            │
│  json_repository · transaction_log · renderer        │
└─────────────────────┬────────────────────────────────┘
                      │
┌─────────────────────▼────────────────────────────────┐
│  Epistemic Kernel — pure Python, no I/O              │
│  types · model · web · invariants · ports            │
└──────────────────────────────────────────────────────┘
```

All mutations route through a single `Gateway`. Both the CLI and the MCP server call the same gateway methods — there is no interface-specific business logic. A bug fixed at the gateway is fixed for every interface simultaneously.

See [ARCHITECTURE.md](ARCHITECTURE.md) for a full technical walkthrough: the entity model, copy-on-write mutation semantics, bidirectional invariant enforcement, every graph traversal method, the full transaction lifecycle, and a concrete end-to-end trace through the stack.

---

## Design Goals

| Goal | Meaning |
|------|---------|
| **Audit scaffold** | Surfaces structural facts. Never prescribes research direction or makes logical judgments |
| **Invariants at write time** | Broken references, cycles, and constraint violations are caught at mutation — not discovered later |
| **Single gateway** | All mutations flow through one boundary. No MCP-specific or CLI-specific business logic |
| **Consumer model** | deSitter records results from researcher-run analyses. It never executes code itself |
| **AI-native interface** | MCP server exposes all capabilities as typed tools. No subprocess, no parsing, full structure |
| **Human parity** | Every MCP tool has a CLI equivalent. Humans get Rich terminal output; scripts get `--json` |
| **Domain-neutral** | Works for physics, ML, medicine, social science. The vocabulary is general empirical reasoning |
| **Minimal dependencies** | Epistemic kernel is stdlib-only. `click` and `rich` for CLI. `fastmcp` is opt-in for MCP |

---

## Package Layout

```
src/desitter/
├── config.py               # ProjectContext, ProjectPaths — runtime configuration contract
├── epistemic/              # Epistemic kernel — pure Python, zero I/O
│   ├── types.py            # Typed IDs, enums, Finding, Severity
│   ├── model.py            # Entity dataclasses: Claim, Assumption, Prediction, …
│   ├── web.py              # EpistemicWeb — aggregate root, all mutations
│   ├── invariants.py       # Ten pure validator functions
│   └── ports.py            # Abstract interfaces: WebRepository, WebValidator, …
├── adapters/               # Infrastructure implementations
│   ├── json_repository.py  # Implements WebRepository over project/data/*.json
│   ├── markdown_renderer.py
│   └── transaction_log.py
├── controlplane/           # Core services
│   ├── gateway.py          # Single mutation/query boundary + GatewayResult
│   ├── factory.py          # Wires concrete adapters into Gateway
│   ├── validate.py
│   ├── check.py            # check_stale, check_refs
│   ├── export.py
│   └── automation.py       # Render-trigger policy table
├── views/                  # Read-only composed summaries
│   ├── health.py           # run_health_check → HealthReport
│   ├── render.py           # SHA-256 fingerprint cache + incremental render
│   ├── status.py           # get_status → ProjectStatus
│   └── metrics.py
└── interfaces/             # Thin adapters — no business logic
    ├── cli/
    │   ├── main.py         # Click command tree
    │   └── formatters.py   # Rich tables + JSON fallback
    └── mcp/
        ├── server.py       # FastMCP entry point
        └── tools.py        # Tool handlers → gateway + view services
```

---

## Development Status

```bash
pip install -e ".[dev]"
pytest
pytest --cov
```

| Phase | Scope | Status |
|---|---|---|
| 1 | Epistemic kernel — `EpistemicWeb`, all entities, ten invariants | **Complete** — 295 tests passing |
| 2 | Persistence, config, packaging | **Partial** — config, transaction log, and automation done; JSON repository and renderer stubbed |
| 3 | Control plane and view services — gateway, validate, health, render | In progress |
| 4 | Interface layer — MCP server and CLI | Pending |
| 5 | Human-first UX — Rich output, `ds inspect` | Pending |
| 6 | Results ingestion — `record_result`, analysis provenance | Pending |
| 7 | Governance — session tracking, close gates (opt-in) | Pending |

The epistemic kernel (Phase 1) is the foundation the rest is built on. It is complete, fully tested, and stable. Layers above it are being built in the order listed.

See [TRACKER.md](TRACKER.md) for the full task-level breakdown.

---

## License

Apache License 2.0 — see [LICENSE](LICENSE).
