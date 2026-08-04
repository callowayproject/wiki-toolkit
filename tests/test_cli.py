"""Smoke tests for the CLI skeleton and the make_source fixture."""

from typing import TYPE_CHECKING

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
