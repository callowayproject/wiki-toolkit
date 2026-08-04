"""Command-line interface for wiki_toolkit.

Commands parse arguments and delegate to wiki_toolkit.core; no business logic lives here.
"""

import click


@click.group()
@click.version_option()
def cli() -> None:
    """AI skills and helper tools that implement and maintain an LLM Wiki."""
