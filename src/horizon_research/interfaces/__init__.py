"""Interface adapters — entry points for all consumers.

All interfaces expose the same service layers (core/, views/).
No business logic lives in any interface module. If a handler does more
than parse input → call service → format output, move the logic up.

Current interfaces:
  cli/   — Click-based CLI for humans and scripts
  mcp/   — FastMCP server for AI agents

Planned interfaces:
  rest/  — REST API adapter (FastAPI or similar)
  gui/   — Desktop or web GUI adapter
  sdk/   — Python library API (horizon_research.record(), etc.)

Adding a new interface means creating a new subdirectory here.
Nothing in core/, views/, or epistemic/ needs to change.
"""
