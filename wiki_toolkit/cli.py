"""Command-line interface for wiki_toolkit.

Commands parse arguments and delegate to wiki_toolkit.core; no business logic lives here.
"""

from dataclasses import asdict
from pathlib import Path

import click

from wiki_toolkit._io import read_jsonl, write_jsonl
from wiki_toolkit.core import build_catalog, lint_wiki, search_catalog
from wiki_toolkit.doctor import run_doctor
from wiki_toolkit.log import ALLOWED_LOG_ACTIONS, append_log_entry, build_log_entry
from wiki_toolkit.sources import (
    ALLOWED_SNAPSHOT_UNITS,
    apply_source_scan,
    compute_source_delta,
    lint_sources,
    scan_sources,
    source_coverage,
    suggest_dedupe,
    write_source_snapshot,
)
from wiki_toolkit.write_gate import ALLOWED_FRAMES, propose_pr


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


@cli.command()
def lint() -> None:
    """Validate wiki note frontmatter, allowed tags, source links, and source_count."""
    docs_dir = Path.cwd() / "docs"
    result = lint_wiki(docs_dir)

    for violation in result.violations:
        click.echo(f"[VIOLATION] {violation.path}: {violation.message}")

    if result.ok:
        click.echo("No lint violations found.")
    else:
        raise SystemExit(1)


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


@cli.command("source-lint")
def source_lint() -> None:
    """Validate docs/sources/ frontmatter and report processed-but-uncovered sources."""
    docs_dir = Path.cwd() / "docs"
    result = lint_sources(docs_dir)

    for violation in result.violations:
        click.echo(f"[VIOLATION] {violation.path}: {violation.message}")

    if result.backlog:
        click.echo("Processed but not yet covered by a wiki note:")
        for source_id in result.backlog:
            click.echo(f"  [backlog] {source_id}")

    if result.ok:
        click.echo("No lint violations found.")
    else:
        raise SystemExit(1)


@cli.command("source-coverage")
def source_coverage_cmd() -> None:
    """Show which docs/sources/ files are covered by at least one wiki note."""
    docs_dir = Path.cwd() / "docs"
    result = source_coverage(docs_dir)

    for entry in result.covered:
        click.echo(f"[COVERED] {entry.path} ({entry.source})")
    for entry in result.uncovered:
        click.echo(f"[UNCOVERED] {entry.path} ({entry.source})")

    click.echo(f"{len(result.covered)} covered, {len(result.uncovered)} uncovered")


@cli.command("source-dedupe")
def source_dedupe() -> None:
    """Suggest which docs/sources/ file to keep per group sharing a source id with a duplicate: true file."""
    docs_dir = Path.cwd() / "docs"
    result = suggest_dedupe(docs_dir)

    for group in result.groups:
        click.echo(f"[GROUP] {group.source}")
        for candidate in group.candidates:
            tag = "KEEP" if candidate.path == group.keep else "DISCARD"
            click.echo(f"  [{tag}] {candidate.path} (similarity={candidate.similarity:.2f})")
        click.echo(f"  suggestion: keep {group.keep} ({group.reason})")

    if result.needs_attention:
        raise SystemExit(1)
    click.echo("No duplicate groups found.")


@cli.command("source-delta")
@click.argument("source")
def source_delta(source: str) -> None:
    """Diff a source's current content against its last-known revision on main."""
    docs_dir = Path.cwd() / "docs"
    try:
        delta = compute_source_delta(docs_dir, source)
    except ValueError as e:
        click.echo(str(e))
        raise SystemExit(1) from e

    if not delta.changed_fields and not delta.new_comment_ids:
        click.echo("No changes since last-known revision.")
        return

    for field_name, (old_value, new_value) in delta.changed_fields.items():
        if old_value is None:
            click.echo(f"[NEW] {field_name}: {new_value!r}")
        else:
            click.echo(f"[CHANGED] {field_name}: {old_value!r} -> {new_value!r}")
    for comment_id in delta.new_comment_ids:
        click.echo(f"[NEW COMMENT] {comment_id}")


@cli.command("source-snapshot")
@click.argument("source")
@click.option(
    "--units", type=click.Choice(ALLOWED_SNAPSHOT_UNITS), required=True, help="Mutation type driving this snapshot."
)
def source_snapshot(source: str, units: str) -> None:
    """Write a new Raw snapshot unit for SOURCE, for a comments or fields mutation."""
    docs_dir = Path.cwd() / "docs"
    try:
        result = write_source_snapshot(docs_dir, source, units)
    except ValueError as e:
        click.echo(str(e))
        raise SystemExit(1) from e

    click.echo(f"Wrote {result.units} snapshot for {result.source} ({result.path}), update_sha={result.update_sha}")


@cli.command("search-catalog")
@click.option("--query", required=True, help="Text to search for in catalog entry titles and paths.")
def search_catalog_cmd(query: str) -> None:
    """Search docs/catalog.jsonl for entries matching --query."""
    docs_dir = Path.cwd() / "docs"
    entries = read_jsonl(docs_dir / "catalog.jsonl")
    matches = search_catalog(query, entries)

    if not matches:
        click.echo("No matches found.")
        return

    for entry in matches:
        click.echo(f"{entry.get('title', '')} ({entry.get('path', '')})")


@cli.command("propose-pr")
@click.option("--pages", required=True, multiple=True, help="Page path to stage. Repeat for multiple pages.")
@click.option("--frame", type=click.Choice(ALLOWED_FRAMES), required=True, help="Reviewer framing for this change.")
def propose_pr_cmd(pages: tuple[str, ...], frame: str) -> None:
    """Stage a wiki change as a local git branch + commit. Never pushes or opens a real PR."""
    try:
        result = propose_pr(Path.cwd(), list(pages), frame)
    except ValueError as e:
        click.echo(str(e))
        raise SystemExit(1) from e

    click.echo(f"Created branch {result.branch} (commit {result.commit_sha[:10]}, frame={result.frame})")
    for page in result.pages:
        click.echo(f"  [staged] {page}")


@cli.command()
@click.option("--title", "message", required=True, help="Short message describing the event.")
@click.option("--details", required=True, help="Additional detail about the event.")
@click.option("--action", type=click.Choice(ALLOWED_LOG_ACTIONS), required=True, help="Event category.")
def log(message: str, details: str, action: str) -> None:
    """Append a structured entry to docs/log.jsonl."""
    docs_dir = Path.cwd() / "docs"
    entry = build_log_entry(action, message, details)
    append_log_entry(docs_dir, entry)

    click.echo(f"Appended {action} entry to docs/log.jsonl")
