"""Non-mutating health check of a wiki's docs/ structure and git clone."""

import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import orjson

from wiki_toolkit.init import PROVENANCE_FILENAME
from wiki_toolkit.settings import ContextConfigSource, diagnose_settings
from wiki_toolkit.sources import SOURCE_MANIFEST_FILENAME

DOCS_DIRS = ("sources", "wiki")
DOCS_FILES = ("catalog.jsonl", "log.jsonl", "schema.md", SOURCE_MANIFEST_FILENAME)
DOCS_STRUCTURE = (*DOCS_FILES, *DOCS_DIRS)
JSONL_FILES_TO_VALIDATE = ("catalog.jsonl", SOURCE_MANIFEST_FILENAME)


@dataclass
class DoctorReport:
    """Result of a `doctor` health check. Non-mutating: built entirely from reads."""

    python_version: str
    docs_dir: Path
    docs_dir_source: ContextConfigSource
    missing_structure: list[str] = field(default_factory=list)
    present_structure: list[str] = field(default_factory=list)
    note_count: int = 0
    is_shallow_clone: bool | None = None
    jsonl_errors: dict[str, list[str]] = field(default_factory=dict)
    skills_version_drift: tuple[str, str] | None = None
    sources: dict[str, ContextConfigSource] = field(default_factory=dict)
    dual_config_files: bool = False
    repo_root_fallback: bool = False
    invalid_sources: dict[str, ContextConfigSource] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        """True if no missing structure, no shallow clone, no malformed JSONL, and no skills version drift."""
        return (
            not self.missing_structure
            and not self.is_shallow_clone
            and not self.jsonl_errors
            and self.skills_version_drift is None
        )


def check_shallow_clone(root: Path) -> bool | None:
    """Return True if `root` is a shallow git clone, False if not, None if not a git repo."""
    git = shutil.which("git")
    if git is None:
        return None
    try:
        result = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
            [git, "rev-parse", "--is-shallow-repository"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError:
        return None
    return result.stdout.strip() == "true"


def validate_jsonl(path: Path) -> list[str]:
    """Return a list of error messages for malformed lines in a JSONL file, empty if well-formed."""
    if not path.is_file():
        return []
    errors = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            orjson.loads(line)
        except orjson.JSONDecodeError as e:
            errors.append(f"line {lineno}: {e}")
    return errors


def check_skills_version_drift(docs_dir: Path) -> tuple[str, str] | None:
    """Compare the local `.agents/skills/.provenance` version to the installed `wiki_toolkit` version.

    Returns `(local_version, installed_version)` if they differ, `None` if they match
    or no local copy's provenance marker exists.
    """
    provenance_path = docs_dir / ".agents" / "skills" / PROVENANCE_FILENAME
    if not provenance_path.is_file():
        return None
    local_version = provenance_path.read_text(encoding="utf-8").strip()
    try:
        installed_version = version("wiki_toolkit")
    except PackageNotFoundError:
        return None
    if local_version == installed_version:
        return None
    return (local_version, installed_version)


def _check_structure(docs_dir: Path, report: DoctorReport) -> None:
    """Populate `report`'s present/missing structure, note count, and JSONL validity."""
    for name in DOCS_FILES:
        if (docs_dir / name).is_file():
            report.present_structure.append(name)
        else:
            report.missing_structure.append(name)
    for name in DOCS_DIRS:
        if (docs_dir / name).is_dir():
            report.present_structure.append(name)
        else:
            report.missing_structure.append(name)

    wiki_dir = docs_dir / "wiki"
    if wiki_dir.is_dir():
        report.note_count = sum(1 for _ in wiki_dir.rglob("*.md"))

    for name in JSONL_FILES_TO_VALIDATE:
        errors = validate_jsonl(docs_dir / name)
        if errors:
            report.jsonl_errors[name] = errors


def run_doctor(
    docs_dir: Path,
    root: Path | None = None,
    docs_dir_source: ContextConfigSource = "default",
    sources: dict[str, ContextConfigSource] | None = None,
    cwd: Path | None = None,
) -> DoctorReport:
    """Run the non-mutating `doctor` health check against `docs_dir`.

    `root` is the git repository root used for the shallow-clone check; it
    defaults to `docs_dir`'s parent, the common case where `docs_dir` is a
    `docs/` subdirectory of the repo.

    `sources` is the full per-field source mapping from `build_context()` (docs_dir,
    repo_root, branch_prefix, batch_byte_cap, batch_file_cap); when given, the report
    also carries settings-resolution warnings (dual config files, a `repo_root` that
    fell back to cwd, any field whose resolved value fell back to default because an
    upstream tier's value was invalid). When omitted, only `docs_dir_source` is tracked,
    matching the tool's pre-settings-diagnostics behavior.
    """
    root = root if root is not None else docs_dir.parent
    report = DoctorReport(
        python_version=sys.version.split()[0],
        docs_dir=docs_dir,
        docs_dir_source=sources["docs_dir"] if sources is not None else docs_dir_source,
        sources=sources if sources is not None else {"docs_dir": docs_dir_source},
    )

    if sources is not None:
        diagnostics = diagnose_settings(sources, cwd=cwd)
        report.dual_config_files = diagnostics.dual_config_files
        report.repo_root_fallback = diagnostics.repo_root_fallback
        report.invalid_sources = diagnostics.invalid_sources

    _check_structure(docs_dir, report)

    report.is_shallow_clone = check_shallow_clone(root)
    report.skills_version_drift = check_skills_version_drift(docs_dir)

    return report
