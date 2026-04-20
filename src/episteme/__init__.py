"""Episteme. Control plane for research epistemic graphs.

Layer cake (top to bottom):
  interfaces: optional consumer adapters (CLI, MCP, REST, …)
  views: read-only summaries and computed projections
  controlplane: orchestration boundary above the epistemic kernel
  epistemic: domain kernel: EpistemicGraph, entities, invariants, ports
  local edge: optional deployment adapters such as local workspaces

Programmatic entry point::

    from episteme.client import EpistemeClient, connect

Attributes:
    __version__ (str): PEP 440 version string for the installed package.
        Follows ``MAJOR.MINOR.PATCH`` semver conventions. Read at runtime
        by tooling and introspection.
"""

__version__ = "0.1.0"

from .client import ClientResult, EpistemeClient, EpistemeClientError, connect
