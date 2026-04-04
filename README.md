# Horizon Research

> **Early Development — not ready for use.**
> The API, file formats, and CLI surface are unstable and will change without notice.
> See [TRACKER.md](TRACKER.md) for current build status.

**An audit scaffold for research epistemic webs.**

Horizon makes the hidden dependency graph of a research project explicit and machine-navigable — claims, assumptions, predictions, analyses, and the invariants that connect them. It does not reason about the research. It gives researchers and AI agents the structure to reason themselves.

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Status: Early Development](https://img.shields.io/badge/status-early%20development-orange.svg)](TRACKER.md)

---

## What It Does

Research projects accumulate a hidden graph of epistemic dependencies: claim C depends on assumption A, prediction P follows from C, analysis S tests P. When that graph is implicit and untracked, it breaks silently — a refuted prediction doesn't update the claims that depend on it, a changed assumption doesn't propagate to its consequences.

Horizon makes that graph explicit and keeps it consistent:

- **Register** claims, assumptions, predictions, analyses, theories, and their relationships
- **Validate** the epistemic web against hard invariants (bidirectional links, DAG structure, tier constraints, coverage)
- **Record** analysis results — Horizon never runs analyses; researchers run them and record the outcome
- **Render** human-readable views (markdown tables, summaries) incrementally
- **Inspect** the web for structural gaps — uncovered claims, untested assumptions, missing derivations
- **Health-check** the project in one command — usable by CI or an AI agent

### The Audit Scaffold Principle

Horizon surfaces structural facts about the epistemic graph. It never makes logical judgments or prescriptive recommendations. The system is the scaffold. The researcher or AI agent is the auditor.

This means:
- `get_structural_gaps` returns observations ("this assumption has no tested_by prediction"), not advice
- `health_check` reports invariant violations, not research strategy
- An AI agent calls traversal tools and applies its own domain knowledge — Horizon provides the map, not the conclusions

The primary interface is an **MCP server** so AI agents (Claude, Cursor, Copilot) can call all operations as typed tools with no subprocess wrangling. A full **CLI** provides the same surface for humans and scripts.

---

## Quick Start

```bash
pip install horizon-research          # CLI + adapters
pip install "horizon-research[mcp]"   # + MCP server
```

```bash
# Initialise a project workspace
horizon init

# Register a claim
horizon register claim '{"id": "C-001", "statement": "...", "type": "foundational", ...}'

# Run all health checks
horizon health

# Inspect structural gaps
horizon inspect

# Start the MCP server (for AI agent use)
horizon-mcp
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for a full technical walkthrough.

---

## Design Goals

| Goal | Description |
|------|-------------|
| **Audit scaffold** | Surfaces structural facts about the epistemic graph; never prescribes research direction |
| **AI-agent first** | MCP server is the primary interface. Agents navigate the web, register artifacts, and validate structure through typed tools |
| **Human parity** | Every MCP operation is also a CLI command. Humans get rich terminal output; scripts get `--json` |
| **Single gateway** | All mutations go through one boundary. No MCP-specific or CLI-specific business logic |
| **Invariants at mutation time** | Broken references, cycles, and bidirectional inconsistencies are caught when introduced — not discovered later |
| **Consumer model** | Horizon records analysis results from researcher-run tools. It never executes analyses itself |
| **Domain-neutral** | Works for physics, ML, medicine, social science. The vocabulary is general empirical reasoning |
| **Zero-friction dependencies** | Epistemic kernel is stdlib-only. `click`/`rich` for CLI UX. `fastmcp` opt-in for MCP |

---

## Architecture Overview

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
│  Core Services (core/) — always available            │
│  gateway · validate · check · export · automation    │
└─────────────────────┬────────────────────────────────┘
                      │
┌─────────────────────▼────────────────────────────────┐
│  Config (config.py) — runtime contract               │
│  HorizonConfig · ProjectContext · ProjectPaths       │
└─────────────────────┬────────────────────────────────┘
                      │
┌─────────────────────▼────────────────────────────────┐
│  Infrastructure Adapters (adapters/)                 │
│  json_repository · transaction_log · markdown_renderer│
└─────────────────────┬────────────────────────────────┘
                      │
┌─────────────────────▼────────────────────────────────┐
│  Epistemic Kernel (epistemic/) — pure Python, no I/O │
│  model · web · invariants · types · ports            │
└──────────────────────────────────────────────────────┘
```

**Dependency rule:** arrows point down only. `interfaces/*` depends on everything below. `epistemic/` depends on nothing above stdlib.

See [ARCHITECTURE.md](ARCHITECTURE.md) for data flow, package layout, design decisions, and the entity model.

---

## Package Layout

```
src/horizon_research/
├── config.py               # HorizonConfig, ProjectContext, load_config(), build_context()
├── epistemic/              # Domain kernel — pure Python, zero I/O
│   ├── types.py            # Typed IDs, enums, Finding
│   ├── model.py            # Entity dataclasses (Claim, Prediction, …)
│   ├── web.py              # EpistemicWeb aggregate root
│   ├── invariants.py       # Cross-entity validation rules
│   └── ports.py            # Abstract interfaces (WebRepository, …)
├── adapters/               # Infrastructure — stdlib only
│   ├── json_repository.py
│   ├── markdown_renderer.py
│   └── transaction_log.py
├── core/                   # Core services — mutations + queries
│   ├── gateway.py          # Single mutation/query boundary
│   ├── validate.py         # Structural validation
│   ├── check.py            # check_stale, check_refs
│   ├── export.py           # Bulk JSON/markdown export
│   └── automation.py       # Render-trigger policy table
├── views/                  # View services — read-only composed summaries
│   ├── health.py           # Composed health report
│   ├── render.py           # Incremental markdown generation
│   ├── status.py           # Summary read model
│   └── metrics.py          # Evidence statistics
└── interfaces/             # Interface adapters — equal peers, no business logic
    ├── cli/                # Humans + scripts
    │   ├── main.py         # Click commands
    │   └── formatters.py   # Rich tables + JSON fallback
    └── mcp/                # AI agents
        ├── server.py       # FastMCP entry point
        └── tools.py        # Tool handlers
```

---

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run tests with coverage
pytest --cov
```

### Build phases

| Phase | Focus | Status |
|-------|-------|--------|
| 1 | Domain core — EpistemicWeb, entities, invariants | In progress |
| 2 | Persistence, config, packaging | Pending |
| 3 | Core and view services (gateway, validate, health, render) | Pending |
| 4 | Interface layer — MCP server + CLI | Pending |
| 5 | Human-first UX (Rich output, `horizon inspect`) | Pending |
| 6 | Results ingestion (record_result, SDK shim) | Pending |
| 7 | Governance — sessions, close gates (opt-in) | Pending |

See [TRACKER.md](TRACKER.md) for the full task-level breakdown.

---

## License

MIT — see [LICENSE](LICENSE).
