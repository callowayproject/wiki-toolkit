"""Shared pytest fixtures for wiki_toolkit tests."""

from typing import TYPE_CHECKING

import frontmatter
import pytest

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


@pytest.fixture
def make_source(tmp_path: Path) -> Callable[..., Path]:
    """Build a minimal Raw source manifest entry under a temp directory.

    Returns a factory that writes a single frontmatter-only markdown file for
    `source` (e.g. "github", "jira") and returns its path. Each call is
    self-contained; tests should not assume a shared "golden wiki" layout.
    """

    def _make_source(source: str, stable_id: str = "test-id", status: str = "resolved", **fields: object) -> Path:
        raw_dir = tmp_path / "Raw" / source
        raw_dir.mkdir(parents=True, exist_ok=True)
        post = frontmatter.Post("", stable_id=stable_id, status=status, **fields)
        path = raw_dir / f"{stable_id}.md"
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
