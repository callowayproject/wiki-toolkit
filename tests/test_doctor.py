"""Unit tests for wiki_toolkit.doctor."""

import shutil
import subprocess
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as pkg_version
from typing import TYPE_CHECKING

from wiki_toolkit.doctor import (
    DOCS_STRUCTURE,
    check_shallow_clone,
    check_skills_version_drift,
    run_doctor,
    validate_jsonl,
)
from wiki_toolkit.init import PROVENANCE_FILENAME
from wiki_toolkit.settings import build_context

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

    report = run_doctor(tmp_path / "docs")

    assert report.missing_structure == []
    assert set(report.present_structure) == set(DOCS_STRUCTURE)


def test_run_doctor_reports_missing_structure(tmp_path: Path) -> None:
    """Absent docs/ elements are reported by name, nothing crashes."""
    (tmp_path / "docs").mkdir()

    report = run_doctor(tmp_path / "docs")

    assert set(report.missing_structure) == set(DOCS_STRUCTURE)
    assert report.present_structure == []
    assert report.ok is False


def test_run_doctor_counts_wiki_notes(tmp_path: Path, make_docs_tree: Callable[[], Path]) -> None:
    """note_count reflects the number of markdown files under docs/wiki/."""
    docs_dir = make_docs_tree()
    (docs_dir / "wiki" / "a.md").write_text("# a")
    (docs_dir / "wiki" / "b.md").write_text("# b")

    report = run_doctor(tmp_path / "docs")

    assert report.note_count == 2


def test_run_doctor_flags_malformed_jsonl(tmp_path: Path, make_docs_tree: Callable[[], Path]) -> None:
    """Malformed lines in catalog.jsonl/source-manifest.jsonl are reported, not raised."""
    docs_dir = make_docs_tree()
    (docs_dir / "catalog.jsonl").write_text('{"path": "a.md"}\nnot json\n')

    report = run_doctor(tmp_path / "docs")

    assert "catalog.jsonl" in report.jsonl_errors
    assert "line 2" in report.jsonl_errors["catalog.jsonl"][0]
    assert report.ok is False


def test_run_doctor_reports_docs_dir_and_source(tmp_path: Path, make_docs_tree: Callable[[], Path]) -> None:
    """The report carries the docs_dir it was given and the source it was told to attribute."""
    make_docs_tree()

    report = run_doctor(tmp_path / "docs", docs_dir_source="env")

    assert report.docs_dir == tmp_path / "docs"
    assert report.docs_dir_source == "env"


def test_check_skills_version_drift_none_when_no_local_copy(make_docs_tree: Callable[[], Path]) -> None:
    """No `.provenance` marker (or no local skills copy at all) means no drift."""
    docs_dir = make_docs_tree()

    assert check_skills_version_drift(docs_dir) is None


def test_check_skills_version_drift_none_when_versions_match(make_docs_tree: Callable[[], Path]) -> None:
    """A `.provenance` marker matching the installed package version reports no drift."""
    docs_dir = make_docs_tree()
    installed = pkg_version("wiki_toolkit")
    (docs_dir / ".agents" / "skills" / PROVENANCE_FILENAME).write_text(installed, encoding="utf-8")

    assert check_skills_version_drift(docs_dir) is None


def test_check_skills_version_drift_reports_mismatch(make_docs_tree: Callable[[], Path]) -> None:
    """A `.provenance` marker older than the installed package reports both versions."""
    docs_dir = make_docs_tree()
    installed = pkg_version("wiki_toolkit")
    (docs_dir / ".agents" / "skills" / PROVENANCE_FILENAME).write_text("0.0.1", encoding="utf-8")

    assert check_skills_version_drift(docs_dir) == ("0.0.1", installed)


def test_check_skills_version_drift_none_when_package_not_installed(
    make_docs_tree: Callable[[], Path], monkeypatch
) -> None:
    """No discoverable `wiki_toolkit` package metadata is treated as no drift, not a crash."""
    docs_dir = make_docs_tree()
    (docs_dir / ".agents" / "skills" / PROVENANCE_FILENAME).write_text("0.0.1", encoding="utf-8")

    def _raise(_name: str) -> str:
        raise PackageNotFoundError

    monkeypatch.setattr("wiki_toolkit.doctor.version", _raise)

    assert check_skills_version_drift(docs_dir) is None


def test_run_doctor_reports_skills_version_drift(tmp_path: Path, make_docs_tree: Callable[[], Path]) -> None:
    """run_doctor surfaces skills version drift and it gates `ok`, without touching local files."""
    docs_dir = make_docs_tree()
    (docs_dir / ".agents" / "skills" / PROVENANCE_FILENAME).write_text("0.0.1", encoding="utf-8")

    report = run_doctor(tmp_path / "docs")

    assert report.skills_version_drift is not None
    assert report.skills_version_drift[0] == "0.0.1"
    assert report.ok is False
    assert (docs_dir / ".agents" / "skills" / PROVENANCE_FILENAME).read_text(encoding="utf-8") == "0.0.1"


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


def test_run_doctor_without_sources_reports_only_docs_dir(tmp_path: Path, make_docs_tree: Callable[[], Path]) -> None:
    """No `sources` given: report.sources holds only docs_dir, and no settings warnings fire."""
    make_docs_tree()

    report = run_doctor(tmp_path / "docs", docs_dir_source="env")

    assert report.sources == {"docs_dir": "env"}
    assert report.dual_config_files is False
    assert report.repo_root_fallback is False
    assert report.invalid_sources == {}


def test_run_doctor_reports_all_five_settings_sources(tmp_path: Path, make_docs_tree: Callable[[], Path]) -> None:
    """With `sources` given, report.sources carries all five settings, not just docs_dir."""
    make_docs_tree()
    (tmp_path / ".git").mkdir()
    _, sources = build_context(cwd=tmp_path)

    report = run_doctor(tmp_path / "docs", root=tmp_path, sources=sources, cwd=tmp_path)

    assert set(report.sources) == {"docs_dir", "repo_root", "branch_prefix", "batch_byte_cap", "batch_file_cap"}


def test_run_doctor_warns_on_dual_config_files(tmp_path: Path, make_docs_tree: Callable[[], Path]) -> None:
    """Both a dedicated file and a pyproject.toml table present is a warning, not a failure."""
    make_docs_tree()
    (tmp_path / ".git").mkdir()
    (tmp_path / ".wiki-toolkit.toml").write_text('branch_prefix = "dedicated/"\n')
    (tmp_path / "pyproject.toml").write_text('[tool.wiki_toolkit]\nbranch_prefix = "py/"\n')
    _, sources = build_context(cwd=tmp_path)

    report = run_doctor(tmp_path / "docs", root=tmp_path, sources=sources, cwd=tmp_path)

    assert report.dual_config_files is True
    assert report.ok is True


def test_run_doctor_no_dual_config_warning_with_only_dedicated_file(
    tmp_path: Path, make_docs_tree: Callable[[], Path]
) -> None:
    """Only the dedicated file present (no pyproject.toml table) is not a dual-config warning."""
    make_docs_tree()
    (tmp_path / ".git").mkdir()
    (tmp_path / ".wiki-toolkit.toml").write_text('branch_prefix = "dedicated/"\n')
    _, sources = build_context(cwd=tmp_path)

    report = run_doctor(tmp_path / "docs", root=tmp_path, sources=sources, cwd=tmp_path)

    assert report.dual_config_files is False


def test_run_doctor_warns_on_repo_root_fallback(tmp_path: Path, make_docs_tree: Callable[[], Path]) -> None:
    """No `.git` found walking up from cwd: repo_root fell back to cwd, reported as a warning."""
    make_docs_tree()
    _, sources = build_context(cwd=tmp_path)

    report = run_doctor(tmp_path / "docs", root=tmp_path, sources=sources, cwd=tmp_path)

    assert report.repo_root_fallback is True
    assert report.ok is True


def test_run_doctor_no_repo_root_fallback_warning_when_git_found(
    tmp_path: Path, make_docs_tree: Callable[[], Path]
) -> None:
    """A `.git` found while walking up from cwd means repo_root's default is not a fallback."""
    make_docs_tree()
    (tmp_path / ".git").mkdir()
    _, sources = build_context(cwd=tmp_path)

    report = run_doctor(tmp_path / "docs", root=tmp_path, sources=sources, cwd=tmp_path)

    assert report.repo_root_fallback is False


def test_run_doctor_warns_on_invalid_promoted_value(tmp_path: Path, make_docs_tree: Callable[[], Path]) -> None:
    """A non-positive batch_byte_cap in the dedicated file falls back to default; doctor names the source."""
    make_docs_tree()
    (tmp_path / ".git").mkdir()
    (tmp_path / ".wiki-toolkit.toml").write_text("batch_byte_cap = -5\n")
    _, sources = build_context(cwd=tmp_path)

    report = run_doctor(tmp_path / "docs", root=tmp_path, sources=sources, cwd=tmp_path)

    assert report.invalid_sources == {"batch_byte_cap": "dedicated_file"}
    assert report.ok is True


def test_run_doctor_no_invalid_source_warning_when_value_is_valid(
    tmp_path: Path, make_docs_tree: Callable[[], Path]
) -> None:
    """A valid dedicated-file value resolving normally produces no invalid_sources entry."""
    make_docs_tree()
    (tmp_path / ".git").mkdir()
    (tmp_path / ".wiki-toolkit.toml").write_text('batch_byte_cap = "5000"\n')
    _, sources = build_context(cwd=tmp_path)

    report = run_doctor(tmp_path / "docs", root=tmp_path, sources=sources, cwd=tmp_path)

    assert report.invalid_sources == {}
