"""MCP server entry point and tool registration.

Builds the FastMCP server, registers all tool handlers from tools.py,
and exposes a run() function as the entry point.

Usage:
    horizon-mcp                           # installed console script
    python -m horizon_research            # via __main__.py
"""
from __future__ import annotations

try:
    import fastmcp
except ImportError as exc:
    raise ImportError(
        "MCP server requires the 'mcp' extra: "
        "pip install 'horizon-research[mcp]'"
    ) from exc

from pathlib import Path

from ...config import build_context, load_config
from .tools import register_tools


def create_server(workspace: Path | None = None) -> fastmcp.FastMCP:
    """Build and return a configured FastMCP server instance.

    workspace: path to the project workspace (defaults to cwd).
    """
    ws = workspace or Path.cwd()
    config = load_config(ws)
    context = build_context(ws, config)

    server = fastmcp.FastMCP(
        name="horizon-research",
        description="Epistemic web data system for research projects",
    )
    register_tools(server, context)
    return server


def run(workspace: Path | None = None) -> None:
    """Create and run the MCP server (blocking)."""
    server = create_server(workspace)
    server.run()


if __name__ == "__main__":
    run()
