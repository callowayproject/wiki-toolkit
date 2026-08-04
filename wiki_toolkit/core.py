"""Business logic for wiki_toolkit, independent of the Click CLI adapter."""

import hashlib
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal

import frontmatter
import orjson

if TYPE_CHECKING:
    from pathlib import Path

DOCS_DIRS = ("sources", "wiki")
SOURCE_MANIFEST_FILENAME = "source-manifest.jsonl"
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


SourceClassification = Literal["new", "update", "duplicate"]


@dataclass
class SourceScanEntry:
    """A single `docs/sources/` file's classification result."""

    source: str
    path: str
    title: str
    classification: SourceClassification
    covered: bool = False
    accepted: bool = True

    @property
    def needs_accept_covered(self) -> bool:
        """True if this is an `update` to an already-covered source that `--accept-covered` would unblock."""
        return self.classification == "update" and self.covered and not self.accepted


@dataclass
class SourceScanResult:
    """The full result of a `source-scan` pass."""

    entries: list[SourceScanEntry] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)  # version-controlled source paths

    @property
    def needs_attention(self) -> bool:
        """True if any entry is a duplicate or an unaccepted covered update."""
        return any(e.classification == "duplicate" or not e.accepted for e in self.entries)


def _read_manifest(manifest_path: Path) -> dict[str, dict]:
    """Read `source-manifest.jsonl` into a dict keyed by `source` id."""
    if not manifest_path.is_file():
        return {}
    manifest: dict[str, dict] = {}
    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        entry = orjson.loads(line)
        manifest[entry["source"]] = entry
    return manifest


def scan_sources(docs_dir: Path, *, accept_covered: bool = False) -> SourceScanResult:
    """Classify each file in `docs_dir/sources/` as new, update, or duplicate.

    Skips version-controlled sources (frontmatter `kind: version_controlled`).
    Within a scan pass, the first-seen file for a `source` id is canonical;
    later files with the same id are classified `duplicate`. A file already
    stamped `duplicate: true` from a prior scan stays excluded regardless of
    scan order, until a human resolves it via `source-dedupe`.
    """
    manifest = _read_manifest(docs_dir / SOURCE_MANIFEST_FILENAME)
    sources_dir = docs_dir / "sources"
    result = SourceScanResult()
    seen: set[str] = set()

    paths = sorted(sources_dir.rglob("*.md")) if sources_dir.is_dir() else []
    for path in paths:
        post = frontmatter.loads(path.read_text(encoding="utf-8"))
        rel_path = str(path.relative_to(docs_dir.parent))

        if post.get("kind") == "version_controlled":
            result.skipped.append(rel_path)
            continue

        source_id = post.get("source")
        if not source_id:
            continue

        classification: SourceClassification
        if post.get("duplicate") or source_id in seen:
            classification = "duplicate"
        elif source_id in manifest:
            classification = "update"
        else:
            classification = "new"
        if classification != "duplicate":
            seen.add(source_id)

        covered = classification == "update" and bool(manifest.get(source_id, {}).get("covered_by"))
        accepted = not (classification == "update" and covered and not accept_covered)

        result.entries.append(
            SourceScanEntry(
                source=source_id,
                path=rel_path,
                title=post.get("title") or path.stem,
                classification=classification,
                covered=covered,
                accepted=accepted,
            )
        )

    return result


def _stamp_frontmatter(path: Path, **fields: object) -> None:
    """Merge `fields` into a source file's frontmatter and write it back."""
    post = frontmatter.loads(path.read_text(encoding="utf-8"))
    for key, value in fields.items():
        post[key] = value
    path.write_bytes(frontmatter.dumps(post).encode())


def apply_source_scan(docs_dir: Path, result: SourceScanResult) -> int:
    """Write a `scan_sources` result: stamp source frontmatter, update the manifest.

    Duplicate files are stamped `duplicate: true` and get no manifest entry.
    Unaccepted (covered, not `--accept-covered`) updates are left untouched.
    Returns the number of manifest entries written.
    """
    manifest = _read_manifest(docs_dir / SOURCE_MANIFEST_FILENAME)
    now = datetime.now(UTC).isoformat()
    written = 0

    for entry in result.entries:
        source_path = docs_dir.parent / entry.path

        if entry.classification == "duplicate":
            _stamp_frontmatter(source_path, duplicate=True)
            continue

        if not entry.accepted:
            continue

        _stamp_frontmatter(source_path, processed=True)

        existing = manifest.get(entry.source, {})
        manifest[entry.source] = {
            "source": entry.source,
            "path": entry.path,
            "title": entry.title,
            "referenced_by": existing.get("referenced_by", []),
            "updated": now,
            "update_sha": hashlib.sha256(source_path.read_bytes()).hexdigest(),
            "status": existing.get("status", "proposed"),
            "covered_by": existing.get("covered_by", []),
        }
        written += 1

    manifest_path = docs_dir / SOURCE_MANIFEST_FILENAME
    lines = [orjson.dumps(manifest[key]).decode() for key in manifest]
    manifest_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

    return written
