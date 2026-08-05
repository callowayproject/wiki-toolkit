"""Source scanning and manifest management for wiki_toolkit."""

import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal

import frontmatter
import orjson
import yaml

from wiki_toolkit._io import read_jsonl, write_jsonl

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

SOURCE_MANIFEST_FILENAME = "source-manifest.jsonl"


SourceClassification = Literal["new", "update", "duplicate"]


@dataclass
class LintViolation:
    """A single rule violation found in a wiki note or source file."""

    path: str
    message: str


@dataclass
class LoadError:
    """A markdown file whose frontmatter failed to parse."""

    message: str


def _iter_markdown(dir_path: Path) -> Iterator[tuple[Path, frontmatter.Post | LoadError]]:
    """Walk `dir_path` for `*.md` files in sorted order, parsing each file's frontmatter.

    Yields `(path, post)` for well-formed files, `(path, LoadError)` for files whose
    YAML frontmatter fails to parse. Yields nothing if `dir_path` doesn't exist.
    """
    if not dir_path.is_dir():
        return
    for path in sorted(dir_path.rglob("*.md")):
        try:
            yield path, frontmatter.loads(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as e:
            yield path, LoadError(message=f"malformed frontmatter: {e}")


def _is_canonical_source(post: frontmatter.Post, seen: set[str]) -> bool:
    """True if `post` is the first-seen, non-duplicate-flagged file for its `source` id.

    Mutates `seen` by recording the source id when canonical. A file stamped
    `duplicate: true`, or a later file sharing an id already in `seen`, is not
    canonical.
    """
    source_id = post.get("source")
    if not source_id or post.get("duplicate") or source_id in seen:
        return False
    seen.add(source_id)
    return True


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
    violations: list[LintViolation] = field(default_factory=list)  # files with malformed frontmatter

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
    scan order, until a human resolves it via `source-dedupe`. A file with
    malformed frontmatter is reported as a violation instead of raising.
    """
    manifest = _read_manifest(docs_dir / SOURCE_MANIFEST_FILENAME)
    sources_dir = docs_dir / "sources"
    result = SourceScanResult()
    seen: set[str] = set()

    for path, post in _iter_markdown(sources_dir):
        rel_path = str(path.relative_to(docs_dir.parent))

        if isinstance(post, LoadError):
            result.violations.append(LintViolation(rel_path, post.message))
            continue

        if post.get("kind") == "version_controlled":
            result.skipped.append(rel_path)
            continue

        source_id = post.get("source")
        if not source_id:
            continue

        canonical = _is_canonical_source(post, seen)
        if not canonical:
            classification: SourceClassification = "duplicate"
        elif source_id in manifest:
            classification = "update"
        else:
            classification = "new"

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

    write_jsonl(docs_dir / SOURCE_MANIFEST_FILENAME, [manifest[key] for key in manifest])

    return written


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

    for path, post in _iter_markdown(docs_dir / "sources"):
        rel_path = str(path.relative_to(docs_dir.parent))

        if isinstance(post, LoadError):
            result.violations.append(LintViolation(rel_path, post.message))
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
    violations: list[LintViolation] = field(default_factory=list)

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
    `catalog.jsonl`'s `sources` lists. Duplicates are excluded using the same
    rule as `scan_sources`: a file stamped `duplicate: true`, or a later file
    sharing a `source` id already seen in this pass. A file with malformed
    frontmatter is reported as a violation instead of raising.
    """
    manifest = _read_manifest(docs_dir / SOURCE_MANIFEST_FILENAME)
    catalog = read_jsonl(docs_dir / "catalog.jsonl")

    covering_notes: dict[str, set[str]] = {}
    for entry in catalog:
        for source_id in entry.get("sources") or []:
            covering_notes.setdefault(source_id, set()).add(entry.get("path", ""))

    result = SourceCoverageResult()
    seen: set[str] = set()
    for path, post in _iter_markdown(docs_dir / "sources"):
        rel_path = str(path.relative_to(docs_dir.parent))

        if isinstance(post, LoadError):
            result.violations.append(LintViolation(rel_path, post.message))
            continue

        if post.get("kind") == "version_controlled":
            continue

        if not _is_canonical_source(post, seen):
            continue

        source_id = post.get("source")
        notes = covering_notes.get(source_id, set()) | set(manifest.get(source_id, {}).get("covered_by", []))
        result.entries.append(
            SourceCoverageEntry(
                source=source_id,
                path=rel_path,
                title=post.get("title") or path.stem,
                covered=bool(notes),
                covered_by=sorted(notes),
            )
        )

    return result
