"""Entry point for `python -m horizon_research`.

Delegates to the Click CLI, so:
    python -m horizon_research <command> [options]
is equivalent to:
    horizon <command> [options]
"""
from horizon_research.interfaces.cli.main import cli

if __name__ == "__main__":
    cli()
