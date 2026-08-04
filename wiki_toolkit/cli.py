"""Command-line interface for wiki_toolkit.

Commands parse arguments and delegate to wiki_toolkit.core; no business logic lives here.
"""

from pathlib import Path

import click

from wiki_toolkit.core import run_doctor


@click.group()
@click.version_option()
def cli() -> None:
    """AI skills and helper tools that implement and maintain an LLM Wiki."""


@cli.command()
def doctor() -> None:
    """Non-mutating health check of the wiki's docs/ structure and git clone."""
    report = run_doctor(Path.cwd())

    click.echo(f"Python: {report.python_version}")
    click.echo(f"Notes in docs/wiki/: {report.note_count}")

    for name in report.present_structure:
        click.echo(f"  [ok] docs/{name}")
    for name in report.missing_structure:
        click.echo(f"  [MISSING] docs/{name}")

    if report.is_shallow_clone is None:
        click.echo("  [warn] not a git repository; cannot check clone depth")
    elif report.is_shallow_clone:
        click.echo("  [warn] shallow git clone detected; source-delta needs full history (fetch-depth: 0)")

    for name, errors in report.jsonl_errors.items():
        for error in errors:
            click.echo(f"  [MALFORMED] docs/{name}: {error}")

    if not report.ok:
        raise SystemExit(1)
