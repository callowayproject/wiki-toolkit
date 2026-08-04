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
