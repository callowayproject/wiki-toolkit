"""Unit tests for wiki_toolkit.write_gate."""

import shutil
import subprocess
from typing import TYPE_CHECKING

from wiki_toolkit.write_gate import commit_pages, propose_pr, stage_paths, start_wiki_branch

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


def test_propose_pr_includes_other_already_staged_files(tmp_path: Path) -> None:
    """A commit contains the listed pages plus anything else already `git add`-ed (self-staged state files)."""
    root = _make_propose_pr_repo(tmp_path)
    (root / "docs" / "wiki" / "note.md").write_text("updated\n")
    other = root / "docs" / "catalog.jsonl"
    other.write_text("catalog\n")
    _git(root, "add", "docs/catalog.jsonl")

    result = propose_pr(root, ["docs/wiki/note.md"], "routine")

    committed_files = _git(root, "show", "--name-only", "--format=", "HEAD").stdout.split()
    assert committed_files == ["docs/catalog.jsonl", "docs/wiki/note.md"]
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


def test_start_wiki_branch_creates_and_checks_out_branch(tmp_path: Path) -> None:
    """start_wiki_branch opens a fresh wiki-update/ branch with nothing committed on it yet."""
    root = _make_propose_pr_repo(tmp_path)
    main_sha = _git(root, "rev-parse", "main").stdout.strip()

    branch = start_wiki_branch(root, "routine")

    assert branch.startswith("wiki-update/routine-")
    assert _git(root, "branch", "--show-current").stdout.strip() == branch
    assert _git(root, "rev-parse", "HEAD").stdout.strip() == main_sha


def test_commit_pages_lands_on_current_branch(tmp_path: Path) -> None:
    """commit_pages adds and commits the given pages onto whatever branch is checked out."""
    root = _make_propose_pr_repo(tmp_path)
    branch = start_wiki_branch(root, "routine")
    (root / "docs" / "wiki" / "note.md").write_text("from batch\n")

    commit_sha = commit_pages(root, ["docs/wiki/note.md"], "Ingest source-1: update note.md")

    assert _git(root, "branch", "--show-current").stdout.strip() == branch
    assert _git(root, "rev-parse", "HEAD").stdout.strip() == commit_sha
    committed_files = _git(root, "show", "--name-only", "--format=", commit_sha).stdout.split()
    assert committed_files == ["docs/wiki/note.md"]


def test_commit_pages_includes_other_already_staged_files(tmp_path: Path) -> None:
    """commit_pages commits the given pages plus any other file already `git add`-ed (self-staged state files)."""
    root = _make_propose_pr_repo(tmp_path)
    start_wiki_branch(root, "routine")
    (root / "docs" / "wiki" / "note.md").write_text("from batch\n")
    other = root / "docs" / "catalog.jsonl"
    other.write_text("catalog\n")
    _git(root, "add", "docs/catalog.jsonl")

    commit_sha = commit_pages(root, ["docs/wiki/note.md"], "Ingest source-1: update note.md")

    committed_files = _git(root, "show", "--name-only", "--format=", commit_sha).stdout.split()
    assert committed_files == ["docs/catalog.jsonl", "docs/wiki/note.md"]


def test_stage_paths_adds_files_to_the_index(tmp_path: Path) -> None:
    """stage_paths git-adds the given paths without committing them."""
    root = _make_propose_pr_repo(tmp_path)
    (root / "docs" / "catalog.jsonl").write_text("catalog\n")

    stage_paths(root, ["docs/catalog.jsonl"])

    staged = _git(root, "diff", "--cached", "--name-only").stdout.split()
    assert staged == ["docs/catalog.jsonl"]


def test_stage_paths_noop_on_empty_list(tmp_path: Path) -> None:
    """stage_paths with an empty list is a no-op, not a git error."""
    root = _make_propose_pr_repo(tmp_path)

    stage_paths(root, [])

    assert not _git(root, "diff", "--cached", "--name-only").stdout.strip()


def test_streaming_batch_commits_land_on_one_branch_without_waiting(tmp_path: Path) -> None:
    """Two batches finishing out of order still each commit immediately, both on the one session branch."""
    root = _make_propose_pr_repo(tmp_path)
    (root / "docs" / "wiki" / "other.md").write_text("other\n")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "add second page")

    branch = start_wiki_branch(root, "routine")

    # Batch "b" (dispatched second) reports back before batch "a" — the coordinator commits
    # it immediately rather than waiting for "a".
    (root / "docs" / "wiki" / "other.md").write_text("from batch b\n")
    commit_b = commit_pages(root, ["docs/wiki/other.md"], "Ingest source-b: update other.md")

    (root / "docs" / "wiki" / "note.md").write_text("from batch a\n")
    commit_a = commit_pages(root, ["docs/wiki/note.md"], "Ingest source-a: update note.md")

    assert commit_b != commit_a
    log = _git(root, "log", "--format=%H", branch).stdout.split()
    assert log[:2] == [commit_a, commit_b]  # newest first
    assert _git(root, "branch", "--show-current").stdout.strip() == branch


def test_propose_pr_reuses_existing_session_branch(tmp_path: Path) -> None:
    """A closing propose_pr call on a branch opened by start_wiki_branch reuses it, no second branch."""
    root = _make_propose_pr_repo(tmp_path)
    branch = start_wiki_branch(root, "routine")
    (root / "docs" / "wiki" / "note.md").write_text("from batch\n")
    commit_pages(root, ["docs/wiki/note.md"], "Ingest source-1: update note.md")

    result = propose_pr(root, ["docs/wiki/note.md"], "routine")

    assert result.branch == branch
    branches = _git(root, "branch", "--list").stdout
    assert branches.count("wiki-update/") == 1


def test_propose_pr_tolerates_pages_already_committed_upstream(tmp_path: Path) -> None:
    """The closing propose_pr call succeeds even when every listed page was already committed by commit_pages."""
    root = _make_propose_pr_repo(tmp_path)
    start_wiki_branch(root, "routine")
    (root / "docs" / "wiki" / "note.md").write_text("from batch\n")
    already_committed_sha = commit_pages(root, ["docs/wiki/note.md"], "Ingest source-1: update note.md")

    result = propose_pr(root, ["docs/wiki/note.md"], "routine")

    assert result.commit_sha == already_committed_sha


def test_propose_pr_commits_other_staged_file_when_reusing_branch(tmp_path: Path) -> None:
    """A closing propose_pr call still commits self-staged state files even when every listed page is done."""
    root = _make_propose_pr_repo(tmp_path)
    start_wiki_branch(root, "routine")
    (root / "docs" / "wiki" / "note.md").write_text("from batch\n")
    commit_pages(root, ["docs/wiki/note.md"], "Ingest source-1: update note.md")
    other = root / "docs" / "catalog.jsonl"
    other.write_text("catalog\n")
    _git(root, "add", "docs/catalog.jsonl")

    result = propose_pr(root, ["docs/wiki/note.md"], "routine")

    committed_files = _git(root, "show", "--name-only", "--format=", result.commit_sha).stdout.split()
    assert committed_files == ["docs/catalog.jsonl"]
