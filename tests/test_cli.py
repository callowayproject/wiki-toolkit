"""Smoke tests for the CLI skeleton and the make_source fixture."""

from click.testing import CliRunner

from wiki_toolkit.cli import cli


def test_cli_group_resolves() -> None:
    """The Click group runs and shows help without error."""
    result = CliRunner().invoke(cli, ["--help"])
    assert result.exit_code == 0


def test_make_source_writes_frontmatter(make_source) -> None:
    """make_source writes a frontmatter file keyed on stable_id."""
    path = make_source("github", stable_id="issue-9", status="proposed")
    assert path.exists()
    assert path.name == "issue-9.md"
