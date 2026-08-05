"""Business logic for wiki_toolkit, independent of the Click CLI adapter."""

import hashlib
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal

import frontmatter
import orjson
import yaml

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


@dataclass
class CatalogEntry:
    """A single `docs/wiki/` note's catalog entry."""

    path: str
    title: str
    updated: str
    sources: list[str]
    status: Literal["resolved", "proposed"]


def build_catalog(docs_dir: Path) -> list[CatalogEntry]:
    """Walk `docs_dir/wiki/`, parsing frontmatter into a catalog entry per note.

    `status` is `resolved` iff every source the note references is `resolved`
    in the source manifest (vacuously true for a note with no sources), else
    `proposed`.
    """
    manifest = _read_manifest(docs_dir / SOURCE_MANIFEST_FILENAME)
    wiki_dir = docs_dir / "wiki"
    entries = []

    paths = sorted(wiki_dir.rglob("*.md")) if wiki_dir.is_dir() else []
    for path in paths:
        post = frontmatter.loads(path.read_text(encoding="utf-8"))
        sources = post.get("sources") or []
        resolved = all(manifest.get(source_id, {}).get("status") == "resolved" for source_id in sources)

        entries.append(
            CatalogEntry(
                path=str(path.relative_to(docs_dir.parent)),
                title=post.get("title") or path.stem,
                updated=post.get("updated", ""),
                sources=sources,
                status="resolved" if resolved else "proposed",
            )
        )

    return entries


@dataclass
class LintViolation:
    """A single rule violation found in a wiki note."""

    path: str
    message: str


@dataclass
class LintResult:
    """The full result of a `lint` pass."""

    violations: list[LintViolation] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """True if no violations were found."""
        return not self.violations


def parse_tag_taxonomy(schema_text: str) -> set[str]:
    """Extract the allowed-tags list from a `## Tag Taxonomy` section in `schema.md`.

    Reads bullet items (`- tag`) between that heading and the next `## ` heading (or EOF).
    """
    tags: set[str] = set()
    in_section = False
    for line in schema_text.splitlines():
        if line.strip().startswith("## "):
            in_section = line.strip() == "## Tag Taxonomy"
            continue
        if in_section and line.strip().startswith("- "):
            tags.add(line.strip()[2:].strip())
    return tags


def lint_wiki(docs_dir: Path) -> LintResult:
    """Validate every note in `docs_dir/wiki/`: frontmatter, tags, source links, `source_count`.

    Tags are checked against the taxonomy in `docs_dir/schema.md` (skipped if that file
    is absent). Sources are checked against `docs_dir/source-manifest.jsonl`.
    """
    result = LintResult()
    manifest = _read_manifest(docs_dir / SOURCE_MANIFEST_FILENAME)

    schema_path = docs_dir / "schema.md"
    allowed_tags = parse_tag_taxonomy(schema_path.read_text(encoding="utf-8")) if schema_path.is_file() else None

    wiki_dir = docs_dir / "wiki"
    paths = sorted(wiki_dir.rglob("*.md")) if wiki_dir.is_dir() else []
    for path in paths:
        rel_path = str(path.relative_to(docs_dir.parent))

        try:
            post = frontmatter.loads(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as e:
            result.violations.append(LintViolation(rel_path, f"malformed frontmatter: {e}"))
            continue

        if allowed_tags is not None:
            for tag in post.get("tags") or []:
                if tag not in allowed_tags:
                    result.violations.append(LintViolation(rel_path, f"disallowed tag: {tag!r}"))

        sources = post.get("sources") or []
        for source_id in sources:
            if source_id not in manifest:
                result.violations.append(LintViolation(rel_path, f"unresolved source reference: {source_id!r}"))

        source_count = post.get("source_count")
        if source_count is not None and source_count != len(sources):
            result.violations.append(
                LintViolation(rel_path, f"source_count is {source_count}, but sources list has {len(sources)}")
            )

    return result


@dataclass
class SourceLintResult:
    """The full result of a `source-lint` pass."""

    violations: list[LintViolation] = field(default_factory=list)
    backlog: list[str] = field(default_factory=list)  # source ids: processed but not yet covered_by any note

    @property
    def ok(self) -> bool:
        """True if no violations were found. Backlog entries don't affect this."""
        return not self.violations


def lint_sources(docs_dir: Path) -> SourceLintResult:
    """Validate every file in `docs_dir/sources/`: required `source` field, `processed`/`duplicate` types.

    Also reports `processed` sources with no `covered_by` entry in `docs_dir/source-manifest.jsonl`
    as a backlog list, distinct from hard errors.
    """
    result = SourceLintResult()
    manifest = _read_manifest(docs_dir / SOURCE_MANIFEST_FILENAME)

    sources_dir = docs_dir / "sources"
    paths = sorted(sources_dir.rglob("*.md")) if sources_dir.is_dir() else []
    for path in paths:
        rel_path = str(path.relative_to(docs_dir.parent))

        try:
            post = frontmatter.loads(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as e:
            result.violations.append(LintViolation(rel_path, f"malformed frontmatter: {e}"))
            continue

        source_id = post.get("source")
        if not source_id:
            result.violations.append(LintViolation(rel_path, "missing required `source` field"))
            continue

        for field_name in ("processed", "duplicate"):
            value = post.get(field_name)
            if value is not None and not isinstance(value, bool):
                result.violations.append(LintViolation(rel_path, f"`{field_name}` must be a boolean, got {value!r}"))

        if post.get("processed") and not manifest.get(source_id, {}).get("covered_by"):
            result.backlog.append(source_id)

    return result


@dataclass
class SourceCoverageEntry:
    """A single `docs/sources/` file's coverage status."""

    source: str
    path: str
    title: str
    covered: bool
    covered_by: list[str] = field(default_factory=list)


@dataclass
class SourceCoverageResult:
    """The full result of a `source-coverage` pass."""

    entries: list[SourceCoverageEntry] = field(default_factory=list)

    @property
    def covered(self) -> list[SourceCoverageEntry]:
        """Entries covered by at least one wiki note."""
        return [e for e in self.entries if e.covered]

    @property
    def uncovered(self) -> list[SourceCoverageEntry]:
        """Entries covered by no wiki note."""
        return [e for e in self.entries if not e.covered]


def source_coverage(docs_dir: Path) -> SourceCoverageResult:
    """Report which `docs_dir/sources/` files are covered by at least one wiki note.

    Cross-references `source-manifest.jsonl`'s `covered_by` field against
    `catalog.jsonl`'s `sources` lists. Duplicate-flagged sources are excluded,
    consistent with `scan_sources`.
    """
    manifest = _read_manifest(docs_dir / SOURCE_MANIFEST_FILENAME)
    catalog = read_jsonl(docs_dir / "catalog.jsonl")

    covering_notes: dict[str, set[str]] = {}
    for entry in catalog:
        for source_id in entry.get("sources") or []:
            covering_notes.setdefault(source_id, set()).add(entry.get("path", ""))

    result = SourceCoverageResult()
    sources_dir = docs_dir / "sources"
    paths = sorted(sources_dir.rglob("*.md")) if sources_dir.is_dir() else []
    for path in paths:
        post = frontmatter.loads(path.read_text(encoding="utf-8"))
        if post.get("duplicate"):
            continue

        source_id = post.get("source")
        if not source_id:
            continue

        notes = covering_notes.get(source_id, set()) | set(manifest.get(source_id, {}).get("covered_by", []))
        result.entries.append(
            SourceCoverageEntry(
                source=source_id,
                path=str(path.relative_to(docs_dir.parent)),
                title=post.get("title") or path.stem,
                covered=bool(notes),
                covered_by=sorted(notes),
            )
        )

    return result


def write_jsonl(path: Path, records: list[dict]) -> None:
    """Write `records` to `path` as JSONL, one object per line."""
    lines = [orjson.dumps(record).decode() for record in records]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def read_jsonl(path: Path) -> list[dict]:
    """Read a JSONL file into a list of dicts. Returns an empty list if the file doesn't exist."""
    if not path.is_file():
        return []
    return [orjson.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def search_catalog(query: str, entries: list[dict]) -> list[dict]:
    """Return catalog entries whose title or path contains `query`, case-insensitively."""
    needle = query.lower()
    return [e for e in entries if needle in e.get("title", "").lower() or needle in e.get("path", "").lower()]


LogAction = Literal["ingest", "update", "lint", "create", "archive", "delete"]
ALLOWED_LOG_ACTIONS: tuple[LogAction, ...] = ("ingest", "update", "lint", "create", "archive", "delete")


@dataclass
class LogEntry:
    """A single `docs/log.jsonl` entry."""

    date: str
    action: LogAction
    message: str
    details: str


def build_log_entry(action: str, message: str, details: str) -> LogEntry:
    """Build a `log.jsonl` entry. Raises ValueError if `action` isn't in the allowed set."""
    if action not in ALLOWED_LOG_ACTIONS:
        raise ValueError(f"invalid action {action!r}; must be one of {ALLOWED_LOG_ACTIONS}")
    return LogEntry(date=datetime.now(UTC).isoformat(), action=action, message=message, details=details)  # type: ignore[arg-type]


def append_log_entry(docs_dir: Path, entry: LogEntry) -> None:
    """Append `entry` as one JSONL line to `docs_dir/log.jsonl`, never rewriting existing lines."""
    docs_dir.mkdir(parents=True, exist_ok=True)
    with (docs_dir / "log.jsonl").open("a", encoding="utf-8") as f:
        f.write(orjson.dumps(asdict(entry)).decode() + "\n")


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

    write_jsonl(docs_dir / SOURCE_MANIFEST_FILENAME, [manifest[key] for key in manifest])

    return written
