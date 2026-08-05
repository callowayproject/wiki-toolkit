"""The write-gate: every wiki mutation routes through here as a staged PR (see docs/design/idea.md)."""

import contextlib
import shutil
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from pathlib import Path

Frame = Literal["routine", "needs-review"]
ALLOWED_FRAMES: tuple[Frame, ...] = ("routine", "needs-review")


@dataclass
class ProposePrResult:
    """Result of staging a wiki change as a local git branch + commit."""

    branch: str
    commit_sha: str
    frame: Frame
    pages: list[str]


def propose_pr(root: Path, pages: list[str], frame: str) -> ProposePrResult:
    """Stage `pages` as a new local git branch + commit, framed for review.

    This is the one write path every wiki mutation is meant to route through
    (see docs/design/idea.md's "write gate" decision). v1 stops at the local
    branch + commit: it never pushes to a remote or opens a real GitHub PR.
    """
    if frame not in ALLOWED_FRAMES:
        raise ValueError(f"invalid frame {frame!r}; must be one of {ALLOWED_FRAMES}")
    if not pages:
        raise ValueError("pages must not be empty")

    git = shutil.which("git")
    if git is None:
        raise ValueError("git executable not found")

    def _run(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
            [git, *args], cwd=root, capture_output=True, text=True, check=True
        )

    branch = f"wiki-update/{frame}-{datetime.now(UTC).strftime('%Y%m%d%H%M%S%f')}"
    label = "Needs review" if frame == "needs-review" else "Routine"
    message = f"{label}: update {', '.join(pages)}"
    original_branch = _run("branch", "--show-current").stdout.strip()

    try:
        _run("checkout", "-b", branch)
        _run("add", "--", *pages)
        # Scope the commit to `pages` even if something else was already staged, so
        # it contains exactly the listed pages, per the acceptance criteria.
        _run("commit", "-m", message, "--", *pages)
        commit_sha = _run("rev-parse", "HEAD").stdout.strip()
    except subprocess.CalledProcessError as e:
        if original_branch:
            with contextlib.suppress(subprocess.CalledProcessError):
                _run("checkout", original_branch)
                _run("branch", "-D", branch)
        raise ValueError(f"git staging failed: {e.stderr.strip()}") from e

    return ProposePrResult(branch=branch, commit_sha=commit_sha, frame=frame, pages=list(pages))  # type: ignore[arg-type]
