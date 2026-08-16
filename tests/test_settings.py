"""Unit tests for wiki_toolkit.settings."""

from typing import TYPE_CHECKING

from wiki_toolkit.settings import build_context, resolve_docs_dir

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


def test_build_context_defaults(tmp_path: Path) -> None:
    """With nothing else set, every field resolves to its built-in default."""
    context, sources = build_context(cwd=tmp_path)

    assert context.docs_dir == tmp_path / "docs"
    assert context.repo_root == tmp_path
    assert context.branch_prefix == "wiki-update/"
    assert context.batch_byte_cap == 100_000
    assert context.batch_file_cap == 20
    assert sources == {
        "docs_dir": "default",
        "repo_root": "default",
        "branch_prefix": "default",
        "batch_byte_cap": "default",
        "batch_file_cap": "default",
    }


def test_build_context_repo_root_walks_up_to_git(tmp_path: Path) -> None:
    """repo_root resolves by walking up from cwd to the nearest `.git`."""
    (tmp_path / ".git").mkdir()
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)

    context, sources = build_context(cwd=nested)

    assert context.repo_root == tmp_path
    assert sources["repo_root"] == "default"


def test_build_context_flag_wins(tmp_path: Path, monkeypatch) -> None:
    """A CLI flag wins over env, dedicated file, and pyproject.toml."""
    monkeypatch.setenv("WIKI_TOOLKIT_DOCS_DIR", str(tmp_path / "env-docs"))
    (tmp_path / ".wiki-toolkit.toml").write_text('docs_dir = "dedicated-docs"\n')

    context, sources = build_context(docs_dir_flag=tmp_path / "flag-docs", cwd=tmp_path)

    assert context.docs_dir == tmp_path / "flag-docs"
    assert sources["docs_dir"] == "flag"


def test_build_context_env_wins_over_dedicated_file(tmp_path: Path, monkeypatch) -> None:
    """A `WIKI_TOOLKIT_*` env var wins over the dedicated file and pyproject.toml."""
    (tmp_path / ".wiki-toolkit.toml").write_text('docs_dir = "dedicated-docs"\n')
    monkeypatch.setenv("WIKI_TOOLKIT_DOCS_DIR", str(tmp_path / "env-docs"))

    context, sources = build_context(cwd=tmp_path)

    assert context.docs_dir == tmp_path / "env-docs"
    assert sources["docs_dir"] == "env"


def test_build_context_all_fields_resolvable_via_env(tmp_path: Path, monkeypatch) -> None:
    """All five fields are uniformly resolvable via `WIKI_TOOLKIT_*` env vars."""
    monkeypatch.setenv("WIKI_TOOLKIT_DOCS_DIR", str(tmp_path / "env-docs"))
    monkeypatch.setenv("WIKI_TOOLKIT_REPO_ROOT", str(tmp_path / "env-repo"))
    monkeypatch.setenv("WIKI_TOOLKIT_BRANCH_PREFIX", "env-prefix/")
    monkeypatch.setenv("WIKI_TOOLKIT_BATCH_BYTE_CAP", "42")
    monkeypatch.setenv("WIKI_TOOLKIT_BATCH_FILE_CAP", "7")

    context, sources = build_context(cwd=tmp_path)

    assert context.docs_dir == tmp_path / "env-docs"
    assert context.repo_root == tmp_path / "env-repo"
    assert context.branch_prefix == "env-prefix/"
    assert context.batch_byte_cap == 42
    assert context.batch_file_cap == 7
    assert all(source == "env" for source in sources.values())


def test_build_context_dedicated_file_wins_over_pyproject(tmp_path: Path) -> None:
    """The dedicated `.wiki-toolkit.toml` wins over `pyproject.toml`'s `[tool.wiki_toolkit]` table."""
    (tmp_path / "pyproject.toml").write_text('[tool.wiki_toolkit]\ndocs_dir = "py-docs"\n')
    (tmp_path / ".wiki-toolkit.toml").write_text('docs_dir = "dedicated-docs"\n')

    context, sources = build_context(cwd=tmp_path)

    assert context.docs_dir == tmp_path / "dedicated-docs"
    assert sources["docs_dir"] == "dedicated_file"


def test_build_context_pyproject_wins_over_default(tmp_path: Path) -> None:
    """`pyproject.toml`'s `[tool.wiki_toolkit]` table wins over the built-in default."""
    (tmp_path / "pyproject.toml").write_text('[tool.wiki_toolkit]\nbranch_prefix = "py-prefix/"\n')

    context, sources = build_context(cwd=tmp_path)

    assert context.branch_prefix == "py-prefix/"
    assert sources["branch_prefix"] == "pyproject"


def test_build_context_malformed_dedicated_file_falls_through(tmp_path: Path) -> None:
    """A `.wiki-toolkit.toml` that fails to parse falls through to pyproject.toml, not raising."""
    (tmp_path / ".wiki-toolkit.toml").write_text("not [ valid toml")
    (tmp_path / "pyproject.toml").write_text('[tool.wiki_toolkit]\ndocs_dir = "py-docs"\n')

    context, sources = build_context(cwd=tmp_path)

    assert context.docs_dir == tmp_path / "py-docs"
    assert sources["docs_dir"] == "pyproject"


def test_build_context_malformed_pyproject_table_falls_through(tmp_path: Path) -> None:
    """A `pyproject.toml` that fails to parse falls through to the built-in default, not raising."""
    (tmp_path / "pyproject.toml").write_text("not [ valid toml")

    context, sources = build_context(cwd=tmp_path)

    assert context.docs_dir == tmp_path / "docs"
    assert sources["docs_dir"] == "default"


def test_build_context_invalid_field_value_falls_back_to_default(tmp_path: Path) -> None:
    """A non-positive batch cap in the dedicated file falls back to the built-in default."""
    (tmp_path / ".wiki-toolkit.toml").write_text("batch_byte_cap = -5\n")

    context, sources = build_context(cwd=tmp_path)

    assert context.batch_byte_cap == 100_000
    assert sources["batch_byte_cap"] == "default"


def test_build_context_empty_branch_prefix_falls_back_to_default(tmp_path: Path) -> None:
    """An empty branch_prefix in the dedicated file falls back to the built-in default."""
    (tmp_path / ".wiki-toolkit.toml").write_text('branch_prefix = ""\n')

    context, sources = build_context(cwd=tmp_path)

    assert context.branch_prefix == "wiki-update/"
    assert sources["branch_prefix"] == "default"


def test_build_context_invalid_env_value_falls_through(tmp_path: Path, monkeypatch) -> None:
    """A non-integer `WIKI_TOOLKIT_BATCH_BYTE_CAP` falls through to the built-in default."""
    monkeypatch.setenv("WIKI_TOOLKIT_BATCH_BYTE_CAP", "not-a-number")

    context, sources = build_context(cwd=tmp_path)

    assert context.batch_byte_cap == 100_000
    assert sources["batch_byte_cap"] == "default"
