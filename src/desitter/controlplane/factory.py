"""Shared gateway wiring factory.

Centralizes the construction of a fully wired Gateway so that both
the MCP server and CLI (and future interfaces) reuse the same logic.
"""
from __future__ import annotations

from ..adapters.json_repository import JsonRepository
from ..adapters.markdown_renderer import MarkdownRenderer
from ..adapters.transaction_log import JsonTransactionLog
from ..config import ProjectContext
from .gateway import Gateway
from .validate import DomainValidator


class _NullProseSync:
    """No-op ProseSync used until the prose sync adapter is implemented."""

    def sync(self, web):
        """Satisfy the ProseSync interface without side effects."""
        return {}


def build_gateway(context: ProjectContext) -> Gateway:
    """Construct a fully wired Gateway from a ProjectContext.

    This is the single composition root for gateway construction.
    Both MCP tools and CLI commands should call this function.
    """
    repo = JsonRepository(context.paths.data_dir)
    validator = DomainValidator()
    renderer = MarkdownRenderer()
    tx_log = JsonTransactionLog(context.paths.transaction_log_file)
    prose_sync = _NullProseSync()
    return Gateway(context, repo, validator, renderer, prose_sync, tx_log)
