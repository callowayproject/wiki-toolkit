"""Unit tests for wiki_toolkit.write_gate."""

import shutil
import subprocess
from typing import TYPE_CHECKING

from wiki_toolkit.write_gate import propose_pr

if TYPE_CHECKING:
    from pathlib import Path

GIT = shutil.which("git") or "git"


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
        [GIT, *args], cwd=root, capture_output=True, text=True, check=True
    )


def _make_propose_pr_repo(tmp_path: Path) -> Path:
    """Build a real git repo with a wiki page committed on main, ready to be edited and staged."""
    (tmp_path / "docs" / "wiki").mkdir(parents=True)
    page = tmp_path / "docs" / "wiki" / "note.md"
    page.write_text("original\n")

    _git(tmp_path, "init", "-b", "main")
    _git(tmp_path, "config", "user.email", "t@t.com")
    _git(tmp_path, "config", "user.name", "t")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "init")

    return tmp_path


def test_propose_pr_creates_branch_and_commits_listed_pages(tmp_path: Path) -> None:
    """propose_pr checks out a new branch and commits exactly the listed pages."""
    root = _make_propose_pr_repo(tmp_path)
    (root / "docs" / "wiki" / "note.md").write_text("updated\n")

    result = propose_pr(root, ["docs/wiki/note.md"], "routine")

    assert result.frame == "routine"
    assert result.pages == ["docs/wiki/note.md"]
    assert result.commit_sha

    current_branch = _git(root, "branch", "--show-current").stdout.strip()
    assert current_branch == result.branch
    assert current_branch != "main"

    committed_files = _git(root, "show", "--name-only", "--format=", "HEAD").stdout.split()
    assert committed_files == ["docs/wiki/note.md"]


def test_propose_pr_needs_review_reflects_frame_in_commit_message(tmp_path: Path) -> None:
    """--frame needs-review is reflected in the commit message, distinct from routine."""
    root = _make_propose_pr_repo(tmp_path)
    (root / "docs" / "wiki" / "note.md").write_text("updated\n")

    result = propose_pr(root, ["docs/wiki/note.md"], "needs-review")

    commit_message = _git(root, "log", "-1", "--format=%s", result.commit_sha).stdout.strip()
    assert "needs review" in commit_message.lower()


def test_propose_pr_never_touches_main_or_a_remote(tmp_path: Path) -> None:
    """propose_pr's new commit lands only on the new local branch; `main` and remotes are untouched."""
    root = _make_propose_pr_repo(tmp_path)
    main_sha_before = _git(root, "rev-parse", "main").stdout.strip()
    (root / "docs" / "wiki" / "note.md").write_text("updated\n")

    propose_pr(root, ["docs/wiki/note.md"], "routine")

    assert _git(root, "rev-parse", "main").stdout.strip() == main_sha_before
    assert not _git(root, "remote").stdout.strip()


def test_propose_pr_ignores_unrelated_staged_changes(tmp_path: Path) -> None:
    """A commit contains exactly the listed pages, even if other files were already `git add`-ed."""
    root = _make_propose_pr_repo(tmp_path)
    (root / "docs" / "wiki" / "note.md").write_text("updated\n")
    other = root / "unrelated.txt"
    other.write_text("unrelated\n")
    _git(root, "add", "unrelated.txt")

    result = propose_pr(root, ["docs/wiki/note.md"], "routine")

    committed_files = _git(root, "show", "--name-only", "--format=", "HEAD").stdout.split()
    assert committed_files == ["docs/wiki/note.md"]
    assert result.pages == ["docs/wiki/note.md"]


def test_propose_pr_restores_original_branch_on_failure(tmp_path: Path) -> None:
    """A failed staging attempt (nonexistent page) leaves the repo back on its original branch, no stray branch."""
    root = _make_propose_pr_repo(tmp_path)

    try:
        propose_pr(root, ["docs/wiki/does-not-exist.md"], "routine")
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for a nonexistent page path")

    assert _git(root, "branch", "--show-current").stdout.strip() == "main"
    branches = _git(root, "branch", "--list").stdout
    assert "wiki-update" not in branches


def test_propose_pr_invalid_frame_raises(tmp_path: Path) -> None:
    """An invalid --frame value raises rather than silently staging with a bogus framing."""
    root = _make_propose_pr_repo(tmp_path)

    try:
        propose_pr(root, ["docs/wiki/note.md"], "bogus")
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for invalid frame")


def test_propose_pr_empty_pages_raises(tmp_path: Path) -> None:
    """An empty pages list raises rather than creating a branch with an empty commit."""
    root = _make_propose_pr_repo(tmp_path)

    try:
        propose_pr(root, [], "routine")
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for empty pages")
