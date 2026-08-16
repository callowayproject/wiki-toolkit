"""Command-line interface for wiki_toolkit.

Commands parse arguments and delegate to wiki_toolkit's domain modules; no business logic lives here.
"""

from dataclasses import asdict
from pathlib import Path

import click
import orjson

from wiki_toolkit._io import read_jsonl, write_jsonl
from wiki_toolkit.batches import plan_batches
from wiki_toolkit.doctor import run_doctor
from wiki_toolkit.init import run_init
from wiki_toolkit.log import ALLOWED_LOG_ACTIONS, append_log_entry, build_log_entry
from wiki_toolkit.settings import Context, build_context
from wiki_toolkit.sources import (
    ALLOWED_SNAPSHOT_UNITS,
    SourceScanResult,
    apply_source_scan,
    compute_source_delta,
    lint_sources,
    scan_sources,
    source_coverage,
    suggest_dedupe,
    write_source_snapshot,
)
from wiki_toolkit.wiki import build_catalog, find_cross_link_candidates, lint_wiki, search_catalog
from wiki_toolkit.write_gate import ALLOWED_FRAMES, commit_pages, propose_pr, start_wiki_branch

_SOURCES_META_KEY = "wiki_toolkit.sources"


@click.group()
@click.option(
    "--docs-dir",
    type=click.Path(path_type=Path, resolve_path=True),
    default=None,
    help="Override the resolved docs/ directory.",
)
@click.option(
    "--repo-root",
    type=click.Path(path_type=Path, resolve_path=True),
    default=None,
    help="Override the resolved repo root.",
)
@click.version_option()
@click.pass_context
def cli(ctx: click.Context, docs_dir: Path | None, repo_root: Path | None) -> None:
    """AI skills and helper tools that implement and maintain an LLM Wiki."""
    context, sources = build_context(docs_dir_flag=docs_dir, repo_root_flag=repo_root)
    ctx.obj = context
    ctx.meta[_SOURCES_META_KEY] = sources


@cli.group()
def config() -> None:
    """Inspect wiki_toolkit's resolved configuration."""


@config.command("show")
@click.pass_context
def config_show(ctx: click.Context) -> None:
    """Print the resolved settings and which source (flag/env/dedicated_file/pyproject/default) each came from."""
    context: Context = ctx.obj
    sources = ctx.meta[_SOURCES_META_KEY]
    for field in Context.model_fields:
        click.echo(f"{field}={getattr(context, field)} (source: {sources[field]})")


@cli.command()
@click.pass_obj
def init(context: Context) -> None:
    """Scaffold a docs/ tree: sources/, wiki/, catalog.jsonl, log.jsonl, source-manifest.jsonl, schema.md."""
    report = run_init(context.docs_dir)

    for name in report.created:
        click.echo(f"  [created] docs/{name}")
    for name in report.already_present:
        click.echo(f"  [already present] docs/{name}")


@cli.command()
@click.pass_context
def doctor(ctx: click.Context) -> None:
    """Non-mutating health check of the wiki's docs/ structure and git clone."""
    context: Context = ctx.obj
    docs_dir_source = ctx.meta[_SOURCES_META_KEY]["docs_dir"]
    report = run_doctor(context.docs_dir, root=context.repo_root, docs_dir_source=docs_dir_source)

    click.echo(f"Python: {report.python_version}")
    click.echo(f"Config: docs_dir={report.docs_dir} (source: {report.docs_dir_source})")
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

    if report.skills_version_drift is not None:
        local_version, installed_version = report.skills_version_drift
        click.echo(
            f"  [warn] docs/.agents/skills copy ({local_version}) and installed wiki_toolkit "
            f"({installed_version}) are out of sync; remove docs/.agents/skills/ and re-run init to refresh"
        )

    if not report.ok:
        raise SystemExit(1)


@cli.command()
@click.pass_obj
def build(context: Context) -> None:
    """Regenerate docs/catalog.jsonl from the current docs/wiki/ notes."""
    result = build_catalog(context.docs_dir)

    catalog_path = context.docs_dir / "catalog.jsonl"
    write_jsonl(catalog_path, [asdict(entry) for entry in result.entries], stage_root=context.repo_root)

    click.echo(f"Wrote {len(result.entries)} entries to docs/catalog.jsonl")


@cli.command()
@click.pass_obj
def lint(context: Context) -> None:
    """Validate wiki note frontmatter, allowed tags, source links, and source_count."""
    result = lint_wiki(context.docs_dir)

    for violation in result.violations:
        click.echo(f"[VIOLATION] {violation.path}: {violation.message}")

    if result.ok:
        click.echo("No lint violations found.")
    else:
        raise SystemExit(1)


@cli.command("batch-plan")
@click.argument("vault", type=click.Path(path_type=Path))
@click.argument("source_dir", type=click.Path(path_type=Path))
@click.pass_obj
def batch_plan_cmd(context: Context, vault: Path, source_dir: Path) -> None:
    """Split the files under SOURCE_DIR into batches for parallel wiki-ingest dispatch."""
    plan = plan_batches(source_dir, context.batch_byte_cap, context.batch_file_cap)
    click.echo(orjson.dumps(asdict(plan)).decode())


@cli.command("source-scan")
@click.option("--update", "update_manifest", is_flag=True, help="Write results into docs/source-manifest.jsonl.")
@click.option("--accept-covered", is_flag=True, help="Accept updates to sources already covered by a wiki note.")
@click.option(
    "--source",
    "source_ids",
    multiple=True,
    help="Limit --update's write/stage step to this source id (repeatable). Omit to write every classified source.",
)
@click.pass_obj
def source_scan(context: Context, update_manifest: bool, accept_covered: bool, source_ids: tuple[str, ...]) -> None:
    """Classify docs/sources/ files as new, update, or duplicate."""
    result = scan_sources(context.docs_dir, accept_covered=accept_covered)

    for entry in result.entries:
        click.echo(f"[{entry.classification.upper()}] {entry.path} ({entry.source})")
        if entry.needs_accept_covered:
            click.echo(f"  needs --accept-covered: {entry.source} is covered by a wiki note")

    for path in result.skipped:
        click.echo(f"[skip] {path} (version-controlled)")

    unmatched: set[str] = set()
    if update_manifest:
        scope, unmatched = calculate_scan_scope(result, source_ids)

        apply_result = apply_source_scan(context.docs_dir, result, source_ids=scope, stage_root=context.repo_root)
        click.echo(f"Wrote {apply_result.written} entries to docs/source-manifest.jsonl")

    if result.needs_attention or unmatched:
        raise SystemExit(1)


def calculate_scan_scope(result: SourceScanResult, source_ids: tuple[str, ...]) -> tuple[set[str] | None, set[str]]:
    """Return the scope of sources to update and the set of unmatched source IDs."""
    scope = set(source_ids) or None
    unmatched = set()
    if scope is not None:
        unmatched = scope - {entry.source for entry in result.entries}
        for source_id in sorted(unmatched):
            click.echo(f"[ERROR] --source {source_id} matched no classified entry")
    return scope, unmatched


@cli.command("source-lint")
@click.pass_obj
def source_lint(context: Context) -> None:
    """Validate docs/sources/ frontmatter and report processed-but-uncovered sources."""
    result = lint_sources(context.docs_dir)

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
@click.pass_obj
def source_coverage_cmd(context: Context) -> None:
    """Show which docs/sources/ files are covered by at least one wiki note."""
    result = source_coverage(context.docs_dir)

    for entry in result.covered:
        click.echo(f"[COVERED] {entry.path} ({entry.source})")
    for entry in result.uncovered:
        click.echo(f"[UNCOVERED] {entry.path} ({entry.source})")

    click.echo(f"{len(result.covered)} covered, {len(result.uncovered)} uncovered")


@cli.command("source-dedupe")
@click.pass_obj
def source_dedupe(context: Context) -> None:
    """Suggest which docs/sources/ file to keep per group sharing a source id with a duplicate: true file."""
    result = suggest_dedupe(context.docs_dir)

    for violation in result.violations:
        click.echo(f"[VIOLATION] {violation.path}: {violation.message}")

    for group in result.groups:
        click.echo(f"[GROUP] {group.source}")
        for candidate in group.candidates:
            tag = "KEEP" if candidate.path == group.keep else "DISCARD"
            click.echo(f"  [{tag}] {candidate.path} (similarity={candidate.similarity:.2f})")
        click.echo(f"  suggestion: keep {group.keep} ({group.reason})")

    if result.needs_attention or result.violations:
        raise SystemExit(1)
    click.echo("No duplicate groups found.")


@cli.command("source-delta")
@click.argument("source")
@click.pass_obj
def source_delta(context: Context, source: str) -> None:
    """Diff a source's current content against its last-known revision on main."""
    try:
        delta = compute_source_delta(context.docs_dir, source)
    except ValueError as e:
        raise click.UsageError(str(e)) from e

    if not delta.changed_fields:
        click.echo("No changes since last-known revision.")
        return

    for field_name, (old_value, new_value) in delta.changed_fields.items():
        if old_value is None:
            click.echo(f"[NEW] {field_name}: {new_value!r}")
        else:
            click.echo(f"[CHANGED] {field_name}: {old_value!r} -> {new_value!r}")


@cli.command("source-snapshot")
@click.argument("source")
@click.option(
    "--units", type=click.Choice(ALLOWED_SNAPSHOT_UNITS), required=True, help="Mutation type driving this snapshot."
)
@click.pass_obj
def source_snapshot(context: Context, source: str, units: str) -> None:
    """Write a new Raw snapshot unit for SOURCE, for a comments or fields mutation."""
    try:
        result = write_source_snapshot(context.docs_dir, source, units, stage_root=context.repo_root)
    except ValueError as e:
        raise click.UsageError(str(e)) from e

    click.echo(f"Wrote {result.units} snapshot for {result.source} ({result.path}), update_sha={result.update_sha}")


@cli.command("search-catalog")
@click.option("--query", required=True, help="Text to search for in catalog entry titles and paths.")
@click.pass_obj
def search_catalog_cmd(context: Context, query: str) -> None:
    """Search docs/catalog.jsonl for entries matching --query."""
    entries = read_jsonl(context.docs_dir / "catalog.jsonl")
    matches = search_catalog(query, entries)

    if not matches:
        click.echo("No matches found.")
        return

    for entry in matches:
        click.echo(f"{entry.get('title', '')} ({entry.get('path', '')})")


@cli.command("cross-link-candidates")
@click.argument("page_paths", nargs=-1, required=True)
@click.pass_obj
def cross_link_candidates_cmd(context: Context, page_paths: tuple[str, ...]) -> None:
    """Find literal title/alias mentions of other catalog pages inside PAGE_PATHS' bodies (JSONL output)."""
    candidates = find_cross_link_candidates(context.docs_dir, list(page_paths))

    for candidate in candidates:
        click.echo(orjson.dumps(asdict(candidate)).decode())


@cli.command("start-branch")
@click.option("--frame", type=click.Choice(ALLOWED_FRAMES), required=True, help="Reviewer framing for this session.")
@click.pass_obj
def start_branch_cmd(context: Context, frame: str) -> None:
    """Open a new local git branch for a batch coordinator session, before any source commits."""
    try:
        branch = start_wiki_branch(context.repo_root, frame, context.branch_prefix)
    except ValueError as e:
        raise click.UsageError(str(e)) from e

    click.echo(branch)


@cli.command("commit-pages")
@click.option("--pages", required=True, multiple=True, help="Page path to commit. Repeat for multiple pages.")
@click.option("--message", required=True, help="Commit message, e.g. naming the source that was just ingested.")
@click.pass_obj
def commit_pages_cmd(context: Context, pages: tuple[str, ...], message: str) -> None:
    """Commit PAGES onto the currently checked-out branch (a batch coordinator's per-source streaming commit)."""
    try:
        commit_sha = commit_pages(context.repo_root, list(pages), message)
    except ValueError as e:
        raise click.UsageError(str(e)) from e

    click.echo(f"Committed {commit_sha[:10]}")
    for page in pages:
        click.echo(f"  [staged] {page}")


@cli.command("propose-pr")
@click.option("--pages", required=True, multiple=True, help="Page path to stage. Repeat for multiple pages.")
@click.option("--frame", type=click.Choice(ALLOWED_FRAMES), required=True, help="Reviewer framing for this change.")
@click.pass_obj
def propose_pr_cmd(context: Context, pages: tuple[str, ...], frame: str) -> None:
    """Stage a wiki change as a local git branch + commit. Never pushes or opens a real PR."""
    try:
        result = propose_pr(context.repo_root, list(pages), frame, context.branch_prefix)
    except ValueError as e:
        raise click.UsageError(str(e)) from e

    click.echo(f"Created branch {result.branch} (commit {result.commit_sha[:10]}, frame={result.frame})")
    for page in result.pages:
        click.echo(f"  [staged] {page}")


@cli.command()
@click.option("--title", "message", required=True, help="Short message describing the event.")
@click.option("--details", required=True, help="Additional detail about the event.")
@click.option("--action", type=click.Choice(ALLOWED_LOG_ACTIONS), required=True, help="Event category.")
@click.pass_obj
def log(context: Context, message: str, details: str, action: str) -> None:
    """Append a structured entry to docs/log.jsonl."""
    entry = build_log_entry(action, message, details)
    append_log_entry(context.docs_dir, entry, stage_root=context.repo_root)

    click.echo(f"Appended {action} entry to docs/log.jsonl")
