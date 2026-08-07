"""Unit tests for wiki_toolkit.settings."""

from typing import TYPE_CHECKING

from wiki_toolkit.settings import resolve_docs_dir

if TYPE_CHECKING:
    from pathlib import Path


def test_resolve_docs_dir_defaults_to_cwd_docs(tmp_path: Path) -> None:
    """With nothing else set, docs_dir is cwd/docs, source is 'default'."""
    result = resolve_docs_dir(cwd=tmp_path)

    assert result.docs_dir == tmp_path / "docs"
    assert result.source == "default"


def test_resolve_docs_dir_reads_pyproject_table(tmp_path: Path) -> None:
    """A [tool.wiki_toolkit] docs_dir in pyproject.toml is used when no flag/env is set."""
    (tmp_path / "pyproject.toml").write_text('[tool.wiki_toolkit]\ndocs_dir = "custom-docs"\n')

    result = resolve_docs_dir(cwd=tmp_path)

    assert result.docs_dir == tmp_path / "custom-docs"
    assert result.source == "pyproject"


def test_resolve_docs_dir_walks_upward_for_pyproject(tmp_path: Path) -> None:
    """The nearest pyproject.toml is found from a nested cwd, same convention as ruff/mypy."""
    (tmp_path / "pyproject.toml").write_text('[tool.wiki_toolkit]\ndocs_dir = "custom-docs"\n')
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)

    result = resolve_docs_dir(cwd=nested)

    assert result.docs_dir == tmp_path / "custom-docs"
    assert result.source == "pyproject"


def test_resolve_docs_dir_env_overrides_pyproject(tmp_path: Path, monkeypatch) -> None:
    """WIKI_TOOLKIT_DOCS_DIR wins over a pyproject.toml table."""
    (tmp_path / "pyproject.toml").write_text('[tool.wiki_toolkit]\ndocs_dir = "custom-docs"\n')
    monkeypatch.setenv("WIKI_TOOLKIT_DOCS_DIR", str(tmp_path / "env-docs"))

    result = resolve_docs_dir(cwd=tmp_path)

    assert result.docs_dir == tmp_path / "env-docs"
    assert result.source == "env"


def test_resolve_docs_dir_flag_overrides_env(tmp_path: Path, monkeypatch) -> None:
    """A CLI flag wins over both env and pyproject.toml."""
    monkeypatch.setenv("WIKI_TOOLKIT_DOCS_DIR", str(tmp_path / "env-docs"))

    result = resolve_docs_dir(flag=tmp_path / "flag-docs", cwd=tmp_path)

    assert result.docs_dir == tmp_path / "flag-docs"
    assert result.source == "flag"


def test_resolve_docs_dir_missing_env_falls_through(tmp_path: Path, monkeypatch) -> None:
    """No env var set falls through to pyproject/default, doesn't error."""
    monkeypatch.delenv("WIKI_TOOLKIT_DOCS_DIR", raising=False)

    result = resolve_docs_dir(cwd=tmp_path)

    assert result.source == "default"


def test_resolve_docs_dir_missing_table_falls_through_to_default(tmp_path: Path) -> None:
    """A pyproject.toml with no [tool.wiki_toolkit] table falls through to default."""
    (tmp_path / "pyproject.toml").write_text('[tool.other]\nfoo = "bar"\n')

    result = resolve_docs_dir(cwd=tmp_path)

    assert result.docs_dir == tmp_path / "docs"
    assert result.source == "default"


def test_resolve_docs_dir_wrong_type_docs_dir_falls_through_to_default(tmp_path: Path) -> None:
    """A [tool.wiki_toolkit] table whose docs_dir isn't a valid path falls through to default."""
    (tmp_path / "pyproject.toml").write_text("[tool.wiki_toolkit]\ndocs_dir = 5\n")

    result = resolve_docs_dir(cwd=tmp_path)

    assert result.docs_dir == tmp_path / "docs"
    assert result.source == "default"


def test_resolve_docs_dir_malformed_toml_falls_through_to_default(tmp_path: Path) -> None:
    """A pyproject.toml that fails to parse falls through to default rather than raising."""
    (tmp_path / "pyproject.toml").write_text("not [ valid toml")

    result = resolve_docs_dir(cwd=tmp_path)

    assert result.docs_dir == tmp_path / "docs"
    assert result.source == "default"
