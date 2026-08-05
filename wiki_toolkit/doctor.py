"""Non-mutating health check of a wiki's docs/ structure and git clone."""

import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import orjson

from wiki_toolkit.core import SOURCE_MANIFEST_FILENAME

if TYPE_CHECKING:
    from pathlib import Path

DOCS_DIRS = ("sources", "wiki")
DOCS_FILES = ("catalog.jsonl", "log.jsonl", "schema.md", SOURCE_MANIFEST_FILENAME)
DOCS_STRUCTURE = (*DOCS_FILES, *DOCS_DIRS)
JSONL_FILES_TO_VALIDATE = ("catalog.jsonl", SOURCE_MANIFEST_FILENAME)


@dataclass
class DoctorReport:
    """Result of a `doctor` health check. Non-mutating: built entirely from reads."""

    python_version: str
    missing_structure: list[str] = field(default_factory=list)
    present_structure: list[str] = field(default_factory=list)
    note_count: int = 0
    is_shallow_clone: bool | None = None
    jsonl_errors: dict[str, list[str]] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        """True if no missing structure, no shallow clone, and no malformed JSONL."""
        return not self.missing_structure and not self.is_shallow_clone and not self.jsonl_errors


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
    errors = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            orjson.loads(line)
        except orjson.JSONDecodeError as e:
            errors.append(f"line {lineno}: {e}")
    return errors


def run_doctor(root: Path) -> DoctorReport:
    """Run the non-mutating `doctor` health check against a wiki rooted at `root`."""
    docs_dir = root / "docs"
    report = DoctorReport(python_version=sys.version.split()[0])

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
        if jsonl_path.is_file():
            errors = validate_jsonl(jsonl_path)
            if errors:
                report.jsonl_errors[name] = errors

    report.is_shallow_clone = check_shallow_clone(root)

    return report
