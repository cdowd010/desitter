"""deSitter (desitter) — control plane for research epistemic webs.

The CLI and MCP server are peer interfaces over the same gateway.
Both route through: controlplane.gateway.Gateway.

Layer cake (top to bottom):
  interfaces      — CLI and MCP adapters
  views           — read-only summaries and rendering services
  controlplane    — orchestration boundary above the epistemic kernel
  epistemic       — domain kernel: EpistemicWeb, entities, invariants, ports
  adapters        — JSON repo, markdown renderer, transaction log

Quick start (programmatic):
  import desitter as ds

  client = connect()
  client.register_claim(
    id="C-001",
    statement="Catalyst X increases yield.",
    type="foundational",
    scope="global",
    falsifiability="A replicated null result would falsify this claim.",
  )
"""

__version__ = "0.1.0"

from .client import ClientResult, DeSitterClient, DeSitterClientError, connect
