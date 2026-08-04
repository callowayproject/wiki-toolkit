"""Smoke tests for the CLI skeleton and the make_source fixture."""

from typing import TYPE_CHECKING

import orjson
from click.testing import CliRunner

from wiki_toolkit.cli import cli

if TYPE_CHECKING:
    from pathlib import Path


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
    lines = (docs_dir / "log.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    entry = orjson.loads(lines[0])
    assert entry["action"] == "ingest"
    assert entry["message"] == "Ingested ticket"
    assert entry["details"] == "jira:ABC-1"
    assert entry["date"]


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
