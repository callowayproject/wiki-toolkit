"""Non-mutating health check of a wiki's docs/ structure and git clone."""

import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import orjson

from wiki_toolkit.init import PROVENANCE_FILENAME
from wiki_toolkit.settings import ConfigSource
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
    docs_dir_source: ConfigSource
    missing_structure: list[str] = field(default_factory=list)
    present_structure: list[str] = field(default_factory=list)
    note_count: int = 0
    is_shallow_clone: bool | None = None
    jsonl_errors: dict[str, list[str]] = field(default_factory=dict)
    skills_version_drift: tuple[str, str] | None = None

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


def run_doctor(docs_dir: Path, root: Path | None = None, docs_dir_source: ConfigSource = "default") -> DoctorReport:
    """Run the non-mutating `doctor` health check against `docs_dir`.

    `root` is the git repository root used for the shallow-clone check; it
    defaults to `docs_dir`'s parent, the common case where `docs_dir` is a
    `docs/` subdirectory of the repo.
    """
    root = root if root is not None else docs_dir.parent
    report = DoctorReport(python_version=sys.version.split()[0], docs_dir=docs_dir, docs_dir_source=docs_dir_source)

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
        jsonl_path = docs_dir / name
        errors = validate_jsonl(jsonl_path)
        if errors:
            report.jsonl_errors[name] = errors

    report.is_shallow_clone = check_shallow_clone(root)
    report.skills_version_drift = check_skills_version_drift(docs_dir)

    return report
