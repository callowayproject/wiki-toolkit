"""Unit tests for wiki_toolkit.core's internal (non-Click) logic."""

import shutil
import subprocess
from typing import TYPE_CHECKING

from wiki_toolkit.core import DOCS_STRUCTURE, check_shallow_clone, run_doctor, validate_jsonl

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

GIT = shutil.which("git") or "git"


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
        [GIT, *args], cwd=root, capture_output=True, text=True, check=True
    )


def test_run_doctor_reports_all_structure_present(tmp_path: Path, make_docs_tree: Callable[[], Path]) -> None:
    """A fully-scaffolded docs/ tree has no missing structure entries."""
    make_docs_tree()

    report = run_doctor(tmp_path)

    assert report.missing_structure == []
    assert set(report.present_structure) == set(DOCS_STRUCTURE)


def test_run_doctor_reports_missing_structure(tmp_path: Path) -> None:
    """Absent docs/ elements are reported by name, nothing crashes."""
    (tmp_path / "docs").mkdir()

    report = run_doctor(tmp_path)

    assert set(report.missing_structure) == set(DOCS_STRUCTURE)
    assert report.present_structure == []
    assert report.ok is False


def test_run_doctor_counts_wiki_notes(tmp_path: Path, make_docs_tree: Callable[[], Path]) -> None:
    """note_count reflects the number of markdown files under docs/wiki/."""
    docs_dir = make_docs_tree()
    (docs_dir / "wiki" / "a.md").write_text("# a")
    (docs_dir / "wiki" / "b.md").write_text("# b")

    report = run_doctor(tmp_path)

    assert report.note_count == 2


def test_run_doctor_flags_malformed_jsonl(tmp_path: Path, make_docs_tree: Callable[[], Path]) -> None:
    """Malformed lines in catalog.jsonl/source-manifest.jsonl are reported, not raised."""
    docs_dir = make_docs_tree()
    (docs_dir / "catalog.jsonl").write_text('{"path": "a.md"}\nnot json\n')

    report = run_doctor(tmp_path)

    assert "catalog.jsonl" in report.jsonl_errors
    assert "line 2" in report.jsonl_errors["catalog.jsonl"][0]
    assert report.ok is False


def test_validate_jsonl_skips_blank_lines(tmp_path: Path) -> None:
    """Blank lines are not treated as malformed."""
    path = tmp_path / "f.jsonl"
    path.write_text('{"a": 1}\n\n{"b": 2}\n')

    assert validate_jsonl(path) == []


def test_check_shallow_clone_none_when_not_a_repo(tmp_path: Path) -> None:
    """A non-git directory reports None (unknown), not an exception."""
    assert check_shallow_clone(tmp_path) is None


def test_check_shallow_clone_false_for_full_clone(tmp_path: Path) -> None:
    """A normal, fully-committed git repo is not shallow."""
    _git(tmp_path, "init")
    (tmp_path / "f.txt").write_text("x")
    _git(tmp_path, "add", "f.txt")
    _git(tmp_path, "-c", "user.email=t@t.com", "-c", "user.name=t", "commit", "-m", "init")

    assert check_shallow_clone(tmp_path) is False


def test_check_shallow_clone_true_for_depth_one_clone(tmp_path: Path) -> None:
    """A depth-1 clone of another repo is reported as shallow."""
    source = tmp_path / "source"
    source.mkdir()
    _git(source, "init")
    (source / "f.txt").write_text("x")
    _git(source, "add", "f.txt")
    _git(source, "-c", "user.email=t@t.com", "-c", "user.name=t", "commit", "-m", "init")

    clone = tmp_path / "clone"
    subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
        [GIT, "clone", "--no-local", "--depth", "1", str(source), str(clone)], capture_output=True, check=True
    )

    assert check_shallow_clone(clone) is True
