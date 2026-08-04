"""Command-line interface for wiki_toolkit.

Commands parse arguments and delegate to wiki_toolkit.core; no business logic lives here.
"""

from dataclasses import asdict
from pathlib import Path

import click

from wiki_toolkit.core import apply_source_scan, build_catalog, run_doctor, scan_sources, write_jsonl


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


@cli.command()
def build() -> None:
    """Regenerate docs/catalog.jsonl from the current docs/wiki/ notes."""
    docs_dir = Path.cwd() / "docs"
    entries = build_catalog(docs_dir)

    write_jsonl(docs_dir / "catalog.jsonl", [asdict(entry) for entry in entries])

    click.echo(f"Wrote {len(entries)} entries to docs/catalog.jsonl")


@cli.command("source-scan")
@click.option("--update", "update_manifest", is_flag=True, help="Write results into docs/source-manifest.jsonl.")
@click.option("--accept-covered", is_flag=True, help="Accept updates to sources already covered by a wiki note.")
def source_scan(update_manifest: bool, accept_covered: bool) -> None:
    """Classify docs/sources/ files as new, update, or duplicate."""
    docs_dir = Path.cwd() / "docs"
    result = scan_sources(docs_dir, accept_covered=accept_covered)

    for entry in result.entries:
        click.echo(f"[{entry.classification.upper()}] {entry.path} ({entry.source})")
        if entry.needs_accept_covered:
            click.echo(f"  needs --accept-covered: {entry.source} is covered by a wiki note")

    for path in result.skipped:
        click.echo(f"[skip] {path} (version-controlled)")

    if update_manifest:
        written = apply_source_scan(docs_dir, result)
        click.echo(f"Wrote {written} entries to docs/source-manifest.jsonl")

    if result.needs_attention:
        raise SystemExit(1)
