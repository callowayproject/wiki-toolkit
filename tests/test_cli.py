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


def test_make_source_writes_frontmatter(make_source) -> None:
    """make_source writes a frontmatter file keyed on stable_id."""
    path = make_source("github", stable_id="issue-9", status="proposed")
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
