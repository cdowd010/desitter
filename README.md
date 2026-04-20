# deSitter

*Versioned, invariant-enforced tracking for the epistemic structure of research.*

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![License: Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Status: Early Development](https://img.shields.io/badge/status-early%20development-orange.svg)](TRACKER.md)

> **Early development — implementation in progress.**
> The API surface and data model are designed and documented; the underlying wiring is not yet complete. See [TRACKER.md](TRACKER.md) for current build status.

---

## What It Is

The scientific method has a structure: you make **claims**, ground them in
**assumptions**, derive **predictions**, run **analyses** to test those
predictions, and record what the evidence shows. That structure exists in every
research project, but it almost never gets tracked. It lives in documents, email
threads, and researcher memory, and it breaks silently.

A refuted prediction doesn't update the claims that depend on it. A revised
assumption doesn't propagate to its consequences. Predictions accumulate that
still cite retracted claims. Assumptions go untested because nobody can see
they're load-bearing. Six months later, nobody can trace why a conclusion was
drawn or whether the underlying support was ever intact. There's no standard
tooling for this — it's a gap that version control, lab notebooks, and project
management software all sidestep.

deSitter fills that gap. It is a versioned, graph-structured registry of your
**epistemic chain** — every claim, assumption, prediction, analysis, and theory
— with hard invariants that keep the graph consistent as research evolves. It
surfaces structural facts about the graph: missing links, untested assumptions,
stale analyses, uncovered predictions.

deSitter is an **audit scaffold**, not a reasoning engine. The researcher, or an
AI agent, decides what to do about what it finds. But it makes the reasoning
visible — and keeps it honest.

---

For researchers, the primary interface is the Python API: `desitter.connect()`
in scripts and notebooks. The MCP server and CLI are deferred until the core
capability is stable; once available, they will enable AI agent workflows and
inspection, health-check, and audit operations respectively.

Every successful mutation is recorded in the append-only transaction log at
`project/data/transaction_log.jsonl` — a first-class public artifact that
external tools can watch, index, and react to directly.

---

## Core Capabilities

- **Register** claims, assumptions, predictions, analyses, theories, and
  parameters in a typed, versioned graph
- **Enforce** referential integrity, DAG acyclicity, bidirectional links, and
  tier constraints at write time, not after the fact
- **Validate** the full epistemic graph on demand against ten domain invariants
- **Track evidence** through prediction tiers (`FULLY_SPECIFIED`, `CONDITIONAL`,
  `FIT_CHECK`) with explicit independence-group accounting
- **Detect staleness** when a parameter changes and propagates to analyses and
  predictions
- **Health-check** the entire project in one command, with a machine-readable
  `HEALTHY / WARNINGS / CRITICAL` result suitable for CI
- **Render** human-readable markdown views of the project graph, incrementally

deSitter never executes analyses. Researchers run their own tools — Python, R,
SageMath, Jupyter — and record outcomes. deSitter records provenance, enforces
structure, and tracks what changed.

---

## Interfaces

deSitter exposes the same core system through multiple interfaces.

**Python API — primary for researchers in scripts and notebooks**

```python
import desitter as ds

client = ds.connect()

client.register_claim(
    id="C-001",
    statement="Catalyst X increases yield.",
    type="foundational",
    scope="global",
    falsifiability="A replicated null result would falsify this claim.",
)
```

**MCP server — primary for AI agent sessions**

The [Model Context Protocol](https://modelcontextprotocol.io) lets AI assistants
(Claude, Copilot, Cursor, and others) call deSitter tools directly as structured
operations. An agent can audit a derivation chain, identify structural gaps,
pre-flight a new prediction with `dry_run=True`, and commit it — all within a
single session. The epistemic graph provides the shared, persistent,
invariant-enforced state. The AI provides the reasoning.

Additional interfaces — CLI, REST, and others — follow the same pattern: thin
adapters over the Gateway, no business logic in the interface layer.

---

## Quick Start

> **Not yet published.** Install from source for development.

```bash
git clone https://github.com/cdowd010/desitter
cd desitter
pip install -e ".[dev]"
```

```python
import desitter as ds

client = ds.connect()

client.register_claim(
    id="C-001",
    statement="Catalyst X increases yield.",
    type="foundational",
    scope="global",
    falsifiability="A replicated null result would falsify this claim.",
)

claims = client.list_claims().data or []
```

```bash
# CLI interface — planned, pending Python API milestone
ds health
ds validate
ds status
```

---

## Architecture

deSitter is built in layers, from the inside out. The innermost layer, the
**epistemic kernel**, is pure Python with no I/O dependencies. It defines the
entity model, the `EpistemicGraph` aggregate root, and all invariant rules. Nothing
in the kernel touches a file, a database, or a network socket.

The layers above the kernel — adapters, control plane, view services, interfaces
— each have a single responsibility and depend only on layers below them.

```
┌──────────────────────────────────────────────────────┐
│  Interface Layer                                     │
│  cli/, humans & scripts    mcp/, AI agents           │
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
│  types · model · graph · invariants · ports            │
└──────────────────────────────────────────────────────┘
```

All mutations route through a single `Gateway`. A bug fixed at the gateway is
fixed for every interface simultaneously.

---

## Design Goals

| Goal | Meaning |
|------|---------|
| **Audit scaffold** | Surfaces structural facts. Never prescribes research direction or makes logical judgments |
| **Invariants at write time** | Broken references, cycles, and constraint violations are caught at mutation, not discovered later |
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
├── config.py               # ProjectContext, ProjectPaths, runtime configuration
├── epistemic/              # Epistemic kernel — pure Python, zero I/O
│   ├── types.py            # Typed IDs, enums, Finding, Severity
│   ├── model.py            # Entity dataclasses: Claim, Assumption, Prediction, …
│   ├── graph.py              # EpistemicGraph, aggregate root, all mutations
│   ├── invariants.py       # Ten pure validator functions
│   ├── codec.py            # Serialization between entities and primitive payloads
│   ├── errors.py           # Domain exception hierarchy: EpistemicError, …
│   └── ports.py            # Abstract interfaces: GraphRepository, GraphValidator, …
├── controlplane/           # Core services
│   ├── gateway.py          # Single mutation/query boundary + GatewayResult
│   ├── _gateway_catalog.py # Resource and query spec tables
│   ├── factory.py          # Wires concrete implementations into Gateway
│   ├── validate.py         # Domain-wide invariant orchestration
│   ├── check.py            # Staleness detection, reference integrity
│   ├── prose.py            # Managed-prose sync and verification
│   ├── render.py           # SHA-256 fingerprint cache + incremental render
│   └── export.py           # Export orchestration
├── client/                 # Python API surface
│   ├── __init__.py         # DeSitterClient, connect()
│   ├── _core.py            # Generic gateway verbs, persistence, context manager
│   └── _resources.py       # Typed entity helpers: register_claim, get_claim, …
├── views/                  # Read-only composed summaries
│   ├── health.py           # run_health_check → HealthReport
│   ├── status.py           # get_status → ProjectStatus
│   └── metrics.py          # compute_metrics → PredictionMetrics, GraphMetrics
└── interfaces/             # Thin adapters, no business logic (planned)
```

Planned but not yet created: `adapters/` (json_repository, transaction_log, markdown_renderer), `interfaces/cli/`, `interfaces/mcp/`.

---

## Development Status

```bash
pip install -e ".[dev]"
pytest
pytest --cov
```

| Milestone | Scope | Status |
|---|---|---|
| 1 | **Python API MVP** — `connect()`, entity register/get/list/transition helpers, `set_*` helpers, `record_analysis_result`, payload schemas | **In progress** |
| 2 | **Shared read-side services** — `validate_project`, `run_health_check`, `get_status`, `compute_metrics`, render, export | Pending |
| 3 | **Interface backfill** — CLI and MCP as thin delegates over the gateway and shared services | Pending |
| 4 | **Documentation and coherence** — align docs with shipped behavior, worked examples, terminology | Pending |

See [TRACKER.md](TRACKER.md) for the full task-level breakdown and exit criteria.

---

## License

Apache License 2.0, see [LICENSE](LICENSE).
