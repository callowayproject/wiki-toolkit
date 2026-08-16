"""The write-gate: every wiki mutation routes through here as a staged PR (see docs/design/idea.md)."""

import contextlib
import shutil
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

Frame = Literal["routine", "needs-review"]
ALLOWED_FRAMES: tuple[Frame, ...] = ("routine", "needs-review")


@dataclass
class ProposePrResult:
    """Result of staging a wiki change as a local git branch + commit."""

    branch: str
    commit_sha: str
    frame: Frame
    pages: list[str]


def _require_git() -> str:
    """Resolve the `git` executable, raising if it isn't on PATH."""
    git = shutil.which("git")
    if git is None:
        raise ValueError("git executable not found")
    return git


def _run(git: str, root: Path, *args: str) -> subprocess.CompletedProcess:
    """Run a `git` subcommand in `root`, raising `CalledProcessError` on a nonzero exit."""
    return subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
        [git, *args], cwd=root, capture_output=True, text=True, check=True
    )


def _new_branch_name(frame: str, branch_prefix: str) -> str:
    """Generate a unique `<branch_prefix><frame>-<timestamp>` branch name."""
    return f"{branch_prefix}{frame}-{datetime.now(UTC).strftime('%Y%m%d%H%M%S%f')}"


def _nothing_staged(git: str, root: Path) -> bool:
    """Report whether the index has no staged diff against HEAD."""
    result = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
        [git, "diff", "--cached", "--quiet"], cwd=root, check=False
    )
    return result.returncode == 0


def stage_paths(root: Path, paths: list[str]) -> None:
    """Git-add `paths` into the index, for a writer to self-stage its own output.

    Called by `stage_best_effort` right after a writer (`write_jsonl`, `append_log_entry`,
    `_stamp_frontmatter`, `SourceManifest.save`) writes its output file(s), so the state
    files a producer command regenerates ride along in the same commit as the pages that
    triggered them (see docs/design/toolkit-spec.md's "Write gate").
    """
    if not paths:
        return
    git = _require_git()
    try:
        _run(git, root, "add", "--", *paths)
    except subprocess.CalledProcessError as e:
        raise ValueError(f"git staging failed: {e.stderr.strip()}") from e


def stage_best_effort(root: Path, paths: list[str]) -> None:
    """Best-effort `stage_paths`: silently no-ops if `root` isn't a git repo (e.g. `init` run standalone).

    Writers call this right after writing their own output, so state files ride along in
    the next commit without a separate call that could fall out of sync (see docs/design/
    toolkit-spec.md's "Write gate").
    """
    with contextlib.suppress(ValueError):
        stage_paths(root, paths)


def start_wiki_branch(root: Path, frame: str, branch_prefix: str) -> str:
    """Create and check out a new local branch for a wiki-update session, before any pages are committed.

    A batch coordinator calls this once, before dispatching any subagents, so every
    per-source `commit_pages` call and the session's closing `propose_pr` call land on
    the same branch (see docs/design/tickets — coordinator mechanism for batch dispatch).
    """
    if frame not in ALLOWED_FRAMES:
        raise ValueError(f"invalid frame {frame!r}; must be one of {ALLOWED_FRAMES}")
    git = _require_git()
    branch = _new_branch_name(frame, branch_prefix)
    _run(git, root, "checkout", "-b", branch)
    return branch


def commit_pages(root: Path, pages: list[str], message: str) -> str:
    """Add `pages` and commit exactly what's currently staged. Returns the commit sha.

    `pages` is added to the index but is no longer a `git commit` pathspec filter — the
    commit picks up anything else already staged too (e.g. `catalog.jsonl`/`log.jsonl`/
    `source-manifest.jsonl`, self-staged by their writers earlier in the same session,
    see `stage_best_effort`), so the state those commands regenerated rides along with
    the pages that triggered them.

    Used for a batch coordinator's streaming per-source commits — each one lands
    immediately on the branch opened by `start_wiki_branch`, without waiting for the
    rest of the session's batches to finish.
    """
    if not pages:
        raise ValueError("pages must not be empty")
    git = _require_git()
    try:
        _run(git, root, "add", "--", *pages)
        _run(git, root, "commit", "-m", message)
    except subprocess.CalledProcessError as e:
        raise ValueError(f"git staging failed: {e.stderr.strip()}") from e
    return _run(git, root, "rev-parse", "HEAD").stdout.strip()


def propose_pr(root: Path, pages: list[str], frame: str, branch_prefix: str) -> ProposePrResult:
    """Stage `pages` as a git branch + commit, framed for review, and return that branch.

    This is the one write path every wiki mutation is meant to route through
    (see docs/design/idea.md's "write gate" decision). v1 stops at the local
    branch + commit: it never pushes to a remote or opens a real GitHub PR.

    `pages` is added to the index but, like `commit_pages`, is no longer a `git commit`
    pathspec filter — the commit picks up exactly what's staged, `pages` included,
    which is how the session's self-staged `catalog.jsonl`/`log.jsonl`/
    `source-manifest.jsonl` writes ride along.

    If the current branch was already opened by `start_wiki_branch` (a batch
    coordinator's session branch), this reuses it instead of creating a new one, and
    tolerates `pages` having nothing left to commit — every page may already have
    landed via that session's streaming `commit_pages` calls, in which case this
    commits whatever else is still staged, if anything.
    """
    if frame not in ALLOWED_FRAMES:
        raise ValueError(f"invalid frame {frame!r}; must be one of {ALLOWED_FRAMES}")
    if not pages:
        raise ValueError("pages must not be empty")

    git = _require_git()
    original_branch = _run(git, root, "branch", "--show-current").stdout.strip()
    reusing_branch = original_branch.startswith(branch_prefix)
    branch = original_branch if reusing_branch else _new_branch_name(frame, branch_prefix)
    label = "Needs review" if frame == "needs-review" else "Routine"
    message = f"{label}: update {', '.join(pages)}"

    try:
        commit_sha = _stage_and_commit(git, root, branch, pages, message, checkout=not reusing_branch)
    except subprocess.CalledProcessError as e:
        if not reusing_branch and original_branch:
            with contextlib.suppress(subprocess.CalledProcessError):
                _run(git, root, "checkout", original_branch)
                _run(git, root, "branch", "-D", branch)
        raise ValueError(f"git staging failed: {e.stderr.strip()}") from e

    return ProposePrResult(branch=branch, commit_sha=commit_sha, frame=frame, pages=list(pages))  # type: ignore[arg-type]


def _stage_and_commit(git: str, root: Path, branch: str, pages: list[str], message: str, *, checkout: bool) -> str:
    """Stage `pages` and commit whatever's staged, optionally checking out `branch` first.

    Returns the resulting commit sha.
    """
    if checkout:
        _run(git, root, "checkout", "-b", branch)
    _run(git, root, "add", "--", *pages)
    # On a reused batch branch, `pages` may already be committed by streaming
    # `commit_pages` calls, and nothing else may be staged either — in that case there's
    # nothing left to commit, and committing would fail for no reason.
    if not checkout and _nothing_staged(git, root):
        return _run(git, root, "rev-parse", "HEAD").stdout.strip()
    _run(git, root, "commit", "-m", message)
    return _run(git, root, "rev-parse", "HEAD").stdout.strip()
