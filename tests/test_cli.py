"""Smoke tests for the CLI skeleton and the make_source fixture."""

import shutil
import subprocess
from typing import TYPE_CHECKING

import orjson
from click.testing import CliRunner

from wiki_toolkit.cli import cli

if TYPE_CHECKING:
    from pathlib import Path

GIT = shutil.which("git") or "git"


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
        [GIT, *args], cwd=root, capture_output=True, text=True, check=True
    )


def test_cli_group_resolves() -> None:
    """The Click group runs and shows help without error."""
    result = CliRunner().invoke(cli, ["--help"])
    assert result.exit_code == 0


def test_make_source_writes_frontmatter(tmp_path: Path, make_source) -> None:
    """make_source writes a frontmatter file keyed on the source id."""
    docs_dir = tmp_path / "docs"
    path = make_source(docs_dir, "github:issue-9", filename="issue-9.md")
    assert path.exists()
    assert path.name == "issue-9.md"


def test_doctor_reports_missing_structure_and_exits_nonzero(tmp_path: Path, monkeypatch) -> None:
    """Doctor delegates to run_doctor and surfaces missing docs/ elements with a nonzero exit."""
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(cli, ["doctor"])

    assert result.exit_code == 1
    assert "MISSING" in result.output
    assert "docs/catalog.jsonl" in result.output


def test_doctor_exits_zero_on_healthy_docs_tree(tmp_path: Path, monkeypatch, make_docs_tree) -> None:
    """Doctor exits 0 and reports no problems against a fully-scaffolded, well-formed docs/ tree."""
    make_docs_tree()
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(cli, ["doctor"])

    assert result.exit_code == 0
    assert "MISSING" not in result.output
    assert "MALFORMED" not in result.output


def test_doctor_reports_resolved_config_and_source(tmp_path: Path, monkeypatch) -> None:
    """Doctor's output includes the resolved docs_dir and which source produced it."""
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(cli, ["doctor"])

    assert f"Config: docs_dir={tmp_path / 'docs'} (source: default)" in result.output


def test_doctor_docs_dir_flag_is_reported_as_source(tmp_path: Path, monkeypatch, make_docs_tree) -> None:
    """A --docs-dir flag overrides resolution and is reported as the 'flag' source."""
    docs_dir = make_docs_tree()
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(cli, ["doctor", "--docs-dir", str(docs_dir)])

    assert f"Config: docs_dir={docs_dir} (source: flag)" in result.output
    assert result.exit_code == 0


def test_config_show_prints_resolved_docs_dir_and_source(tmp_path: Path, monkeypatch) -> None:
    """`config show` prints the resolved docs_dir and its source, without mutating anything."""
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(cli, ["config", "show"])

    assert result.exit_code == 0
    assert f"docs_dir={tmp_path / 'docs'} (source: default)" in result.output


def test_config_show_honors_docs_dir_flag(tmp_path: Path, monkeypatch) -> None:
    """`config show --docs-dir` reports the flag value with source 'flag'."""
    monkeypatch.chdir(tmp_path)
    override = tmp_path / "other-docs"

    result = CliRunner().invoke(cli, ["config", "show", "--docs-dir", str(override)])

    assert result.exit_code == 0
    assert f"docs_dir={override} (source: flag)" in result.output


def test_build_writes_catalog(tmp_path: Path, monkeypatch, make_docs_tree, make_wiki_note) -> None:
    """Build writes one catalog entry per note in docs/wiki/ and exits 0."""
    docs_dir = make_docs_tree()
    make_wiki_note(docs_dir, "a.md", title="A Page", updated="2026-01-01", sources=[])
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(cli, ["build"])

    assert result.exit_code == 0
    assert "Wrote 1 entries" in result.output
    lines = (docs_dir / "catalog.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    entry = orjson.loads(lines[0])
    assert entry == {
        "path": "docs/wiki/a.md",
        "title": "A Page",
        "updated": "2026-01-01",
        "sources": [],
        "status": "resolved",
    }


def test_build_skips_malformed_note_without_crashing(
    tmp_path: Path, monkeypatch, make_docs_tree, make_wiki_note
) -> None:
    """Build exits 0 and still catalogs well-formed notes when one note has malformed frontmatter."""
    docs_dir = make_docs_tree()
    make_wiki_note(docs_dir, "a.md", title="A Page")
    (docs_dir / "wiki" / "bad.md").write_text("---\ntitle: [unclosed\n---\nbody")
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(cli, ["build"])

    assert result.exit_code == 0
    assert "Wrote 1 entries" in result.output
    lines = (docs_dir / "catalog.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert orjson.loads(lines[0])["path"] == "docs/wiki/a.md"


def test_build_overwrites_existing_catalog(tmp_path: Path, monkeypatch, make_docs_tree, make_wiki_note) -> None:
    """Build regenerates docs/catalog.jsonl from scratch rather than appending."""
    docs_dir = make_docs_tree()
    (docs_dir / "catalog.jsonl").write_text('{"path": "stale.md"}\n')
    make_wiki_note(docs_dir, "a.md", title="A Page")
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(cli, ["build"])

    assert result.exit_code == 0
    catalog = (docs_dir / "catalog.jsonl").read_text(encoding="utf-8")
    assert "stale.md" not in catalog
    assert "A Page" in catalog


def test_source_scan_reports_new_source(tmp_path: Path, monkeypatch, make_docs_tree, make_source) -> None:
    """source-scan reports a classification line for a new source and exits 0."""
    docs_dir = make_docs_tree()
    make_source(docs_dir, "jira:ABC-1")
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(cli, ["source-scan"])

    assert result.exit_code == 0
    assert "NEW" in result.output
    assert "jira:ABC-1" in result.output


def test_source_scan_update_writes_manifest(tmp_path: Path, monkeypatch, make_docs_tree, make_source) -> None:
    """--update writes classification results into docs/source-manifest.jsonl."""
    docs_dir = make_docs_tree()
    (docs_dir / "source-manifest.jsonl").write_text("")
    make_source(docs_dir, "jira:ABC-1")
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(cli, ["source-scan", "--update"])

    assert result.exit_code == 0
    manifest = (docs_dir / "source-manifest.jsonl").read_text(encoding="utf-8")
    assert "jira:ABC-1" in manifest


def test_lint_exits_zero_on_clean_wiki(tmp_path: Path, monkeypatch, make_docs_tree, make_wiki_note) -> None:
    """Lint exits 0 and reports no violations against a clean docs/wiki/ tree."""
    docs_dir = make_docs_tree()
    (docs_dir / "schema.md").write_text("## Tag Taxonomy\n\n- infra\n")
    make_wiki_note(docs_dir, "a.md", tags=["infra"], sources=[])
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(cli, ["lint"])

    assert result.exit_code == 0
    assert "No lint violations" in result.output


def test_lint_reports_violation_and_exits_nonzero(tmp_path: Path, monkeypatch, make_docs_tree, make_wiki_note) -> None:
    """Lint reports a disallowed tag and exits nonzero."""
    docs_dir = make_docs_tree()
    (docs_dir / "schema.md").write_text("## Tag Taxonomy\n\n- infra\n")
    make_wiki_note(docs_dir, "a.md", tags=["bogus"], sources=[])
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(cli, ["lint"])

    assert result.exit_code == 1
    assert "bogus" in result.output


def test_source_scan_flags_duplicate_with_nonzero_exit(
    tmp_path: Path, monkeypatch, make_docs_tree, make_source
) -> None:
    """A duplicate source id is reported and exits nonzero, signalling it needs manual resolution."""
    docs_dir = make_docs_tree()
    make_source(docs_dir, "jira:ABC-1", filename="a-first.md")
    make_source(docs_dir, "jira:ABC-1", filename="b-second.md")
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(cli, ["source-scan"])

    assert result.exit_code == 1
    assert "DUPLICATE" in result.output


def test_source_dedupe_exits_zero_with_no_duplicates(tmp_path: Path, monkeypatch, make_docs_tree, make_source) -> None:
    """source-dedupe reports nothing to resolve and exits 0 when there are no duplicate-flagged files."""
    docs_dir = make_docs_tree()
    make_source(docs_dir, "jira:ABC-1")
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(cli, ["source-dedupe"])

    assert result.exit_code == 0
    assert "No duplicate groups found." in result.output


def test_source_dedupe_lists_group_and_keep_suggestion(
    tmp_path: Path, monkeypatch, make_docs_tree, make_source
) -> None:
    """source-dedupe groups duplicate-flagged files by source id and prints a keep/discard suggestion."""
    docs_dir = make_docs_tree()
    make_source(docs_dir, "jira:ABC-1", filename="a-first.md")
    make_source(docs_dir, "jira:ABC-1", filename="b-second.md", duplicate=True)
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(cli, ["source-dedupe"])

    assert result.exit_code == 1
    assert "[GROUP] jira:ABC-1" in result.output
    assert "[KEEP]" in result.output
    assert "[DISCARD]" in result.output


def test_source_dedupe_never_modifies_files(tmp_path: Path, monkeypatch, make_docs_tree, make_source) -> None:
    """source-dedupe is suggestion-only: it never deletes or rewrites the files it reports on."""
    docs_dir = make_docs_tree()
    path_a = make_source(docs_dir, "jira:ABC-1", filename="a-first.md")
    path_b = make_source(docs_dir, "jira:ABC-1", filename="b-second.md", duplicate=True)
    before_a, before_b = path_a.read_text(encoding="utf-8"), path_b.read_text(encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    CliRunner().invoke(cli, ["source-dedupe"])

    assert path_a.read_text(encoding="utf-8") == before_a
    assert path_b.read_text(encoding="utf-8") == before_b


def test_source_dedupe_reports_violations_and_exits_nonzero(tmp_path: Path, monkeypatch, make_docs_tree) -> None:
    """source-dedupe prints malformed-frontmatter violations and exits nonzero, even with no duplicate groups."""
    docs_dir = make_docs_tree()
    (docs_dir / "sources" / "bad.md").write_text("---\nsource: [unclosed\n---\nbody")
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(cli, ["source-dedupe"])

    assert result.exit_code == 1
    assert "[VIOLATION] docs/sources/bad.md" in result.output
    assert "malformed frontmatter" in result.output


def test_source_lint_exits_zero_on_clean_tree(tmp_path: Path, monkeypatch, make_docs_tree, make_source) -> None:
    """source-lint exits 0 and reports no violations against a clean docs/sources/ tree."""
    docs_dir = make_docs_tree()
    make_source(docs_dir, "jira:ABC-1")
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(cli, ["source-lint"])

    assert result.exit_code == 0
    assert "No lint violations" in result.output


def test_source_lint_flags_violation_and_exits_nonzero(tmp_path: Path, monkeypatch, make_docs_tree) -> None:
    """source-lint reports a missing `source` field and exits nonzero."""
    docs_dir = make_docs_tree()
    (docs_dir / "sources" / "a.md").write_text("---\ntitle: no source id\n---\nbody")
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(cli, ["source-lint"])

    assert result.exit_code == 1
    assert "missing required" in result.output


def test_source_lint_reports_backlog_without_failing(tmp_path: Path, monkeypatch, make_docs_tree, make_source) -> None:
    """source-lint lists processed-but-uncovered sources as backlog and still exits 0."""
    docs_dir = make_docs_tree()
    (docs_dir / "source-manifest.jsonl").write_text(orjson.dumps({"source": "jira:ABC-1"}).decode() + "\n")
    make_source(docs_dir, "jira:ABC-1", processed=True)
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(cli, ["source-lint"])

    assert result.exit_code == 0
    assert "jira:ABC-1" in result.output
    assert "backlog" in result.output.lower()


def test_source_coverage_reports_covered_and_uncovered(
    tmp_path: Path, monkeypatch, make_docs_tree, make_source
) -> None:
    """source-coverage lists covered and uncovered sources and exits 0."""
    docs_dir = make_docs_tree()
    (docs_dir / "source-manifest.jsonl").write_text("")
    make_source(docs_dir, "jira:ABC-1", filename="covered.md")
    make_source(docs_dir, "jira:ABC-2", filename="uncovered.md")
    entry = {"path": "docs/wiki/foo.md", "sources": ["jira:ABC-1"]}
    (docs_dir / "catalog.jsonl").write_text(orjson.dumps(entry).decode() + "\n")
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(cli, ["source-coverage"])

    assert result.exit_code == 0
    assert "[COVERED] docs/sources/covered.md (jira:ABC-1)" in result.output
    assert "[UNCOVERED] docs/sources/uncovered.md (jira:ABC-2)" in result.output
    assert "1 covered, 1 uncovered" in result.output


def test_search_catalog_returns_matching_entry(tmp_path: Path, monkeypatch, make_docs_tree) -> None:
    """search-catalog finds an entry by title and exits 0."""
    docs_dir = make_docs_tree()
    entry = {"path": "docs/wiki/auth.md", "title": "Auth Middleware", "sources": [], "updated": "", "status": "ok"}
    (docs_dir / "catalog.jsonl").write_text(orjson.dumps(entry).decode() + "\n")
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(cli, ["search-catalog", "--query", "auth"])

    assert result.exit_code == 0
    assert "Auth Middleware" in result.output
    assert "docs/wiki/auth.md" in result.output


def test_search_catalog_no_matches_is_not_an_error(tmp_path: Path, monkeypatch, make_docs_tree) -> None:
    """A query with no matches prints a clear empty result and exits 0."""
    docs_dir = make_docs_tree()
    entry = {"path": "docs/wiki/auth.md", "title": "Auth Middleware", "sources": [], "updated": "", "status": "ok"}
    (docs_dir / "catalog.jsonl").write_text(orjson.dumps(entry).decode() + "\n")
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(cli, ["search-catalog", "--query", "nonexistent"])

    assert result.exit_code == 0
    assert "No matches found." in result.output


def test_search_catalog_requires_query_option(tmp_path: Path, monkeypatch, make_docs_tree) -> None:
    """Omitting --query is a usage error, not a crash."""
    make_docs_tree()
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(cli, ["search-catalog"])

    assert result.exit_code != 0


def test_log_appends_entry(tmp_path: Path, monkeypatch, make_docs_tree) -> None:
    """Log writes one well-formed entry to docs/log.jsonl and exits 0."""
    docs_dir = make_docs_tree()
    (docs_dir / "log.jsonl").write_text("")
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(
        cli, ["log", "--title", "Ingested ticket", "--details", "jira:ABC-1", "--action", "ingest"]
    )

    assert result.exit_code == 0
    assert "Appended ingest entry to docs/log.jsonl" in result.output
    lines = (docs_dir / "log.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    entry = orjson.loads(lines[0])
    assert entry["action"] == "ingest"
    assert entry["message"] == "Ingested ticket"
    assert entry["details"] == "jira:ABC-1"
    assert entry["date"]


def test_log_creates_docs_dir_if_missing(tmp_path: Path, monkeypatch) -> None:
    """Log succeeds even if docs/ doesn't exist yet, rather than crashing."""
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(cli, ["log", "--title", "x", "--details", "y", "--action", "create"])

    assert result.exit_code == 0
    assert (tmp_path / "docs" / "log.jsonl").is_file()


def test_log_preserves_existing_entries(tmp_path: Path, monkeypatch, make_docs_tree) -> None:
    """Log never rewrites or reorders existing docs/log.jsonl entries."""
    docs_dir = make_docs_tree()
    first_entry = {"date": "2026-01-01T00:00:00", "action": "create", "message": "first", "details": ""}
    (docs_dir / "log.jsonl").write_text(orjson.dumps(first_entry).decode() + "\n")
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(cli, ["log", "--title", "second", "--details", "", "--action", "update"])

    assert result.exit_code == 0
    lines = (docs_dir / "log.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert orjson.loads(lines[0])["message"] == "first"
    assert orjson.loads(lines[1])["message"] == "second"


def test_log_rejects_invalid_action(tmp_path: Path, monkeypatch, make_docs_tree) -> None:
    """An --action outside the allowed set is a usage error, not a crash."""
    make_docs_tree()
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(cli, ["log", "--title", "x", "--details", "y", "--action", "bogus"])

    assert result.exit_code != 0


def test_source_delta_reports_changed_field(tmp_path: Path, monkeypatch, make_docs_tree, make_source) -> None:
    """source-delta prints changed fields and exits 0 for a known source with a real prior commit."""
    docs_dir = make_docs_tree()
    make_source(docs_dir, "jira:ABC-1", filename="abc-1.md", status="open")
    (docs_dir / "source-manifest.jsonl").write_text(
        orjson.dumps({"source": "jira:ABC-1", "path": "docs/sources/abc-1.md"}).decode() + "\n"
    )
    _git(tmp_path, "init", "-b", "main")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "-c", "user.email=t@t.com", "-c", "user.name=t", "commit", "-m", "init")
    make_source(docs_dir, "jira:ABC-1", filename="abc-1.md", status="closed")
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(cli, ["source-delta", "jira:ABC-1"])

    assert result.exit_code == 0
    assert "status: 'open' -> 'closed'" in result.output


def test_source_delta_no_prior_commit_labels_fields_new(
    tmp_path: Path, monkeypatch, make_docs_tree, make_source
) -> None:
    """A first-time source's fields print as [NEW], not [CHANGED], since there's no prior value."""
    docs_dir = make_docs_tree()
    make_source(docs_dir, "jira:NEW-1", filename="new-1.md", status="open")
    (docs_dir / "source-manifest.jsonl").write_text(
        orjson.dumps({"source": "jira:NEW-1", "path": "docs/sources/new-1.md"}).decode() + "\n"
    )
    _git(tmp_path, "init", "-b", "main")
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(cli, ["source-delta", "jira:NEW-1"])

    assert result.exit_code == 0
    assert "[NEW] status: 'open'" in result.output
    assert "[CHANGED]" not in result.output


def test_source_delta_unknown_source_exits_nonzero(tmp_path: Path, monkeypatch, make_docs_tree) -> None:
    """source-delta on a source with no manifest entry is a clean error, not a crash."""
    make_docs_tree()
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(cli, ["source-delta", "jira:MISSING"])

    assert result.exit_code == 1
    assert "jira:MISSING" in result.output


def test_source_snapshot_fields_resets_processed_and_exits_zero(
    tmp_path: Path, monkeypatch, make_docs_tree, make_source
) -> None:
    """source-snapshot --units fields resets processed and reports the write."""
    docs_dir = make_docs_tree()
    make_source(docs_dir, "jira:ABC-1", filename="abc-1.md", processed=True, status="open")
    (docs_dir / "source-manifest.jsonl").write_text(
        orjson.dumps({"source": "jira:ABC-1", "path": "docs/sources/abc-1.md"}).decode() + "\n"
    )
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(cli, ["source-snapshot", "jira:ABC-1", "--units", "fields"])

    assert result.exit_code == 0
    assert "Wrote fields snapshot for jira:ABC-1" in result.output


def test_source_snapshot_rejects_invalid_units(tmp_path: Path, monkeypatch, make_docs_tree, make_source) -> None:
    """An unrecognized --units value is a usage error, not a crash."""
    docs_dir = make_docs_tree()
    make_source(docs_dir, "jira:ABC-1", filename="abc-1.md")
    (docs_dir / "source-manifest.jsonl").write_text(
        orjson.dumps({"source": "jira:ABC-1", "path": "docs/sources/abc-1.md"}).decode() + "\n"
    )
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(cli, ["source-snapshot", "jira:ABC-1", "--units", "bogus"])

    assert result.exit_code != 0


def test_source_snapshot_unknown_source_exits_nonzero(tmp_path: Path, monkeypatch, make_docs_tree) -> None:
    """source-snapshot on a source with no manifest entry is a clean error, not a crash."""
    make_docs_tree()
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(cli, ["source-snapshot", "jira:MISSING", "--units", "comments"])

    assert result.exit_code == 1
    assert "jira:MISSING" in result.output


def _make_propose_pr_repo(tmp_path: Path) -> None:
    """Build a real git repo with a wiki page committed on main, ready to be edited and staged."""
    (tmp_path / "docs" / "wiki").mkdir(parents=True)
    page = tmp_path / "docs" / "wiki" / "note.md"
    page.write_text("original\n")

    _git(tmp_path, "init", "-b", "main")
    _git(tmp_path, "config", "user.email", "t@t.com")
    _git(tmp_path, "config", "user.name", "t")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "init")


def test_propose_pr_routine_exits_zero_and_reports_branch(tmp_path: Path, monkeypatch) -> None:
    """propose-pr --frame routine parses --pages, stages the commit, and exits 0."""
    _make_propose_pr_repo(tmp_path)
    (tmp_path / "docs" / "wiki" / "note.md").write_text("updated\n")
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(cli, ["propose-pr", "--pages", "docs/wiki/note.md", "--frame", "routine"])

    assert result.exit_code == 0
    assert "frame=routine" in result.output
    assert "[staged] docs/wiki/note.md" in result.output


def test_propose_pr_accepts_repeated_pages_option(tmp_path: Path, monkeypatch) -> None:
    """--pages can be repeated to stage multiple pages in one commit."""
    _make_propose_pr_repo(tmp_path)
    second_page = tmp_path / "docs" / "wiki" / "second.md"
    second_page.write_text("second\n")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "-c", "user.email=t@t.com", "-c", "user.name=t", "commit", "-m", "add second")
    (tmp_path / "docs" / "wiki" / "note.md").write_text("updated\n")
    second_page.write_text("updated second\n")
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(
        cli,
        ["propose-pr", "--pages", "docs/wiki/note.md", "--pages", "docs/wiki/second.md", "--frame", "needs-review"],
    )

    assert result.exit_code == 0
    assert "[staged] docs/wiki/note.md" in result.output
    assert "[staged] docs/wiki/second.md" in result.output


def test_propose_pr_rejects_invalid_frame(tmp_path: Path, monkeypatch) -> None:
    """An unrecognized --frame value is a usage error, not a crash."""
    _make_propose_pr_repo(tmp_path)
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(cli, ["propose-pr", "--pages", "docs/wiki/note.md", "--frame", "bogus"])

    assert result.exit_code != 0


def test_propose_pr_never_pushes_or_opens_a_remote_pr(tmp_path: Path, monkeypatch) -> None:
    """propose-pr's write stays entirely local: no remote is configured or touched."""
    _make_propose_pr_repo(tmp_path)
    (tmp_path / "docs" / "wiki" / "note.md").write_text("updated\n")
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(cli, ["propose-pr", "--pages", "docs/wiki/note.md", "--frame", "routine"])

    assert result.exit_code == 0
    assert not _git(tmp_path, "remote").stdout.strip()


def test_doctor_reports_clean_bill_of_health_on_a_populated_full_clone(
    tmp_path: Path, monkeypatch, make_docs_tree, make_source, make_wiki_note
) -> None:
    """Doctor exits 0 with no warnings against a real, non-shallow repo after source-scan and build."""
    docs_dir = make_docs_tree()
    make_source(docs_dir, "github:issue-1", title="Issue 1")
    make_wiki_note(docs_dir, "issue-1.md", title="Issue 1 Note", updated="2026-01-01", sources=["github:issue-1"])

    _git(tmp_path, "init", "-b", "main")
    _git(tmp_path, "config", "user.email", "t@t.com")
    _git(tmp_path, "config", "user.name", "t")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "init")
    monkeypatch.chdir(tmp_path)

    scan_result = CliRunner().invoke(cli, ["source-scan", "--update"])
    assert scan_result.exit_code == 0

    build_result = CliRunner().invoke(cli, ["build"])
    assert build_result.exit_code == 0

    result = CliRunner().invoke(cli, ["doctor"])

    assert result.exit_code == 0
    assert "MISSING" not in result.output
    assert "MALFORMED" not in result.output
    assert "shallow" not in result.output
    assert "not a git repository" not in result.output
