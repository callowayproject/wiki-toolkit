"""Shared pytest fixtures for wiki_toolkit tests."""

from typing import TYPE_CHECKING

import frontmatter
import pytest

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


@pytest.fixture
def make_source() -> Callable[..., Path]:
    """Build a Raw source file under a docs/ tree's `sources/` directory.

    Returns a factory that writes a single frontmatter markdown file keyed on
    the `source` identifier and returns its path. Each call is self-contained;
    tests should not assume a shared "golden wiki" layout.
    """

    def _make_source(
        docs_dir: Path, source: str, *, filename: str | None = None, processed: bool = False, **fields: object
    ) -> Path:
        sources_dir = docs_dir / "sources"
        sources_dir.mkdir(parents=True, exist_ok=True)
        post = frontmatter.Post("", source=source, processed=processed, **fields)
        name = filename or f"{source.replace('/', '-').replace(':', '-')}.md"
        path = sources_dir / name
        path.write_bytes(frontmatter.dumps(post).encode())
        return path

    return _make_source


@pytest.fixture
def make_docs_tree(tmp_path: Path) -> Callable[[], Path]:
    """Build a minimal, well-formed docs/ tree (all structure elements present, JSONL valid)."""

    def _make_docs_tree() -> Path:
        docs_dir = tmp_path / "docs"
        (docs_dir / "sources").mkdir(parents=True)
        (docs_dir / "wiki").mkdir(parents=True)
        (docs_dir / "catalog.jsonl").write_text('{"path": "a.md"}\n')
        (docs_dir / "log.jsonl").write_text("")
        (docs_dir / "schema.md").write_text("# schema")
        (docs_dir / "source-manifest.jsonl").write_text('{"source": "s1"}\n')
        return docs_dir

    return _make_docs_tree
