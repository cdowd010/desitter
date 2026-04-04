# deSitter

> **Early Development — not ready for use.**
> The API, file formats, and CLI surface are unstable and will change without notice.
> See [TRACKER.md](TRACKER.md) for current build status.

## The Scientific Method as Code

The scientific method has a structure: you make **claims**, ground them in **assumptions**, derive **predictions**, run **analyses** to test those predictions, and record what the evidence shows. That structure exists in every research project — but it almost never gets tracked. It lives in Notion pages, email threads, and researcher memory, and it breaks silently. A refuted prediction doesn't update the claims that depend on it. A revised assumption doesn't propagate to its consequences. Nobody can tell, six months later, why a conclusion was drawn.

deSitter makes that structure explicit and machine-enforceable. It is a versioned, graph-structured registry of your epistemic chain — every claim, assumption, prediction, analysis, and theory, with the invariants that hold them together.

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![License: Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Status: Early Development](https://img.shields.io/badge/status-early%20development-orange.svg)](TRACKER.md)

---

## Built for AI Agent Swarms

The primary interface is an [MCP server](https://modelcontextprotocol.io) — the protocol that lets AI agents call typed tools directly. This is intentional.

The long-term vision is a research environment where a **swarm of AI agents** collaborates on a single project: one agent audits derivation chains, another identifies structural gaps, a third proposes new predictions, and a fourth validates that everything is still consistent — all working against the same shared epistemic web, simultaneously. The graph provides the coordination layer. The invariants ensure no agent can introduce inconsistencies. The audit trail records every mutation.

Today, a single Claude or Copilot session can already do this:

```
Agent: call register_claim(...)      → "registered C-042"
Agent: call run_health_check()       → "3 invariant violations found"
Agent: call get_structural_gaps()    → "Assumption A-007 has no tested predictions"
Agent: call get_derivation_chain("C-042") → [full chain back to foundational claims]
```

No subprocess wrangling. No screen scraping. Each operation is a structured tool call with typed arguments and a structured response. The CLI provides the same surface for humans and scripts.

---

## What It Does

deSitter makes the epistemic graph of a research project explicit and keeps it consistent:

- **Register** claims, assumptions, predictions, analyses, theories, and their relationships
- **Validate** the epistemic web against hard invariants (bidirectional links, DAG structure, tier constraints, coverage)
- **Record** analysis results — deSitter never runs analyses; researchers run them and record the outcome
- **Render** human-readable views (markdown tables, summaries) incrementally
- **Inspect** the web for structural gaps — uncovered claims, untested assumptions, missing derivations
- **Health-check** the project in one command — usable by CI or an AI agent

### The Audit Scaffold Principle

deSitter surfaces structural facts about the epistemic graph. It never makes logical judgments or prescriptive recommendations. The system is the scaffold. The researcher or AI agent is the auditor.

This means:
- `get_structural_gaps` returns observations ("this assumption has no tested_by prediction"), not advice
- `health_check` reports invariant violations, not research strategy
- An AI agent calls traversal tools and applies its own domain knowledge — deSitter provides the map, not the conclusions

---

## Quick Start

```bash
pip install desitter          # CLI + adapters
pip install "desitter[mcp]"   # + MCP server
```

```bash
# Initialise a project workspace
ds init

# Register a claim
ds register claim '{"id": "C-001", "statement": "...", "type": "foundational", ...}'

# Run all health checks
ds health

# Inspect structural gaps
ds inspect

# Start the MCP server (for AI agent use)
ds-mcp
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
| **Consumer model** | deSitter records analysis results from researcher-run tools. It never executes analyses itself |
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
│  Core Services (controlplane/) — always available            │
│  gateway · validate · check · export · automation    │
└─────────────────────┬────────────────────────────────┘
                      │
┌─────────────────────▼────────────────────────────────┐
│  Config (config.py) — runtime contract               │
│  DesitterConfig · ProjectContext · ProjectPaths       │
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
src/desitter/
├── config.py               # DesitterConfig, ProjectContext, load_config(), build_context()
├── epistemic/              # Domain kernel — pure Python, zero I/O
│   ├── types.py            # Typed IDs, enums, Finding
│   ├── model.py            # Entity dataclasses (Claim, Prediction, …)
│   ├── web.py              # EpistemicWeb aggregate root
│   ├── invariants.py       # Cross-entity validation rules
│   └── ports.py            # Abstract interfaces (WebRepository, …)
├── adapters/               # Infrastructure — stdlib only
│   ├── json_repository.py
│   ├── markdown_renderer.py
│   └── transaction_log.py  # implemented
├── controlplane/                   # Core services — mutations + queries
│   ├── gateway.py          # Single mutation/query boundary
│   ├── validate.py         # Structural validation
│   ├── check.py            # check_stale, check_refs
│   ├── export.py           # Bulk JSON/markdown export
│   └── automation.py       # Render-trigger policy table (implemented)
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
| 1 | Domain core — EpistemicWeb, entities, invariants | **Complete — 295 tests passing** |
| 2 | Persistence, config, packaging | **Partial** — `config.py`, `transaction_log.py`, `automation.py` done; JSON repo + renderer stubbed |
| 3 | Core and view services (gateway, validate, health, render) | Pending |
| 4 | Interface layer — MCP server + CLI | Pending |
| 5 | Human-first UX (Rich output, `ds inspect`) | Pending |
| 6 | Results ingestion (record_result, SDK shim) | Pending |
| 7 | Governance — sessions, close gates (opt-in) | Pending |

See [TRACKER.md](TRACKER.md) for the full task-level breakdown.

---

## License

Apache License 2.0 — see [LICENSE](LICENSE).
