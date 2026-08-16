"""Source scanning and manifest management for wiki_toolkit."""

import hashlib
import shutil
import subprocess
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Literal, overload

import orjson
import yaml

from wiki_toolkit._io import read_jsonl, write_jsonl
from wiki_toolkit.frontmatter import Post
from wiki_toolkit.write_gate import stage_best_effort

SOURCE_MANIFEST_FILENAME = "source-manifest.jsonl"


SourceClassification = Literal["new", "update", "duplicate"]


@dataclass
class LintViolation:
    """A single rule violation found in a wiki note or source file."""

    path: str
    message: str


@dataclass
class LoadError:
    """A Markdown file whose frontmatter failed to parse."""

    message: str


def _iter_markdown(dir_path: Path) -> Iterator[tuple[Path, Post | LoadError]]:
    """Walk `dir_path` for `*.md` files in sorted order, parsing each file's frontmatter.

    Yields `(path, post)` for well-formed files, `(path, LoadError)` for files whose
    YAML frontmatter fails to parse. Yields nothing if `dir_path` doesn't exist.
    """
    if not dir_path.is_dir():
        return
    for path in sorted(dir_path.rglob("*.md")):
        try:
            yield path, Post.loads(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as e:
            yield path, LoadError(message=f"malformed frontmatter: {e}")


def _load_or_record_violation(
    path: Path, post: Post | LoadError, violations: list[LintViolation], docs_dir: Path
) -> Post | None:
    """Return `post` if well-formed, else append a `LintViolation` to `violations` and return None."""
    if isinstance(post, LoadError):
        rel_path = str(path.relative_to(docs_dir.parent))
        violations.append(LintViolation(rel_path, post.message))
        return None
    return post


def _is_canonical_source(post: Post, seen: set[str]) -> bool:
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


class SourceManifest:
    """A `source`-keyed view over `source-manifest.jsonl`, loaded once and saved explicitly."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._entries: dict[str, dict] = {}
        if path.is_file():
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                entry = orjson.loads(line)
                self._entries[entry["source"]] = entry

    def __getitem__(self, source: str) -> dict:
        return self._entries[source]

    def __setitem__(self, source: str, entry: dict) -> None:
        if entry.get("source") != source:
            raise ValueError(f"entry['source'] {entry.get('source')!r} must match key {source!r}")
        self._entries[source] = entry

    def __contains__(self, source: str) -> bool:
        return source in self._entries

    def __iter__(self) -> Iterator[str]:
        return iter(self._entries)

    @overload
    def get(self, source: str) -> dict | None: ...
    @overload
    def get(self, source: str, default: dict) -> dict: ...

    def get(self, source: str, default: dict | None = None) -> dict | None:
        """Return the entry for `source`, or `default` if it's not in the manifest."""
        return self._entries.get(source, default)

    def save(self, *, stage_root: Path | None = None) -> None:
        """Write current entries back to `source-manifest.jsonl`.

        If `stage_root` is given, best-effort git-stages the manifest right after writing it.
        """
        write_jsonl(self._path, [self._entries[key] for key in self._entries], stage_root=stage_root)


def _resolve_source_entry(manifest: SourceManifest, source: str) -> dict:
    """Return `manifest[source]`, or raise `ValueError` if the source is unknown."""
    entry = manifest.get(source)
    if entry is None:
        raise ValueError(f"unknown source: {source!r}")
    return entry


def scan_sources(docs_dir: Path, *, accept_covered: bool = False) -> SourceScanResult:
    """Classify each file in `docs_dir/sources/` as new, update, or duplicate.

    Skips version-controlled sources (frontmatter `kind: version_controlled`).
    Within a scan pass, the first-seen file for a `source` id is canonical;
    later files with the same id are classified `duplicate`. A file already
    stamped `duplicate: true` from a prior scan stays excluded regardless of
    scan order, until a human resolves it via `source-dedupe`. A file with
    malformed frontmatter is reported as a violation instead of raising.
    """
    manifest = SourceManifest(docs_dir / SOURCE_MANIFEST_FILENAME)
    sources_dir = docs_dir / "sources"
    result = SourceScanResult()
    seen: set[str] = set()

    for path, raw_post in _iter_markdown(sources_dir):
        post = _load_or_record_violation(path, raw_post, result.violations, docs_dir)
        if post is None:
            continue
        rel_path = str(path.relative_to(docs_dir.parent))

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
                title=post.get("title") or manifest.get(source_id, {}).get("title") or path.stem,
                classification=classification,
                covered=covered,
                accepted=accepted,
            )
        )

    return result


def _stamp_frontmatter(path: Path, *, stage_root: Path | None = None, **fields: Any) -> None:
    """Merge `fields` into a source file's frontmatter and write it back.

    If `stage_root` is given, best-effort git-stages `path` right after writing it.
    """
    post = Post.loads(path.read_text(encoding="utf-8"))
    for key, value in fields.items():
        post[key] = value
    path.write_bytes(Post.dumps(post).encode())
    if stage_root is not None:
        stage_best_effort(stage_root, [str(path)])


@dataclass
class ApplySourceScanResult:
    """What `apply_source_scan` actually wrote/stamped."""

    written: int  # number of manifest entries written
    touched_paths: list[str] = field(default_factory=list)  # every file stamped, duplicate or manifest-written


def apply_source_scan(
    docs_dir: Path, result: SourceScanResult, *, source_ids: set[str] | None = None, stage_root: Path | None = None
) -> ApplySourceScanResult:
    """Write a `scan_sources` result: stamp source frontmatter, update the manifest.

    Duplicate files are stamped `duplicate: true` and get no manifest entry.
    Unaccepted (covered, not `--accept-covered`) updates are left untouched.
    `source_ids`, if given, narrows the write/stamp step to only those source ids —
    every other classified entry is skipped, unwritten until a later unscoped call.
    If `stage_root` is given, every file this writes is best-effort git-staged — one
    `git add` per touched file rather than a single batched call, trading a few extra
    subprocess spawns for staging that can't drift out of sync with the write.
    """
    manifest = SourceManifest(docs_dir / SOURCE_MANIFEST_FILENAME)
    now = datetime.now(UTC).isoformat()
    written = 0
    touched_paths: list[str] = []

    for entry in result.entries:
        if source_ids is not None and entry.source not in source_ids:
            continue

        source_path = docs_dir.parent / entry.path

        if entry.classification == "duplicate":
            _stamp_frontmatter(source_path, duplicate=True, stage_root=stage_root)
            touched_paths.append(entry.path)
            continue

        if not entry.accepted:
            continue

        _stamp_frontmatter(source_path, processed=True, stage_root=stage_root)
        touched_paths.append(entry.path)

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

    manifest.save(stage_root=stage_root)

    return ApplySourceScanResult(written=written, touched_paths=touched_paths)


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
    manifest = SourceManifest(docs_dir / SOURCE_MANIFEST_FILENAME)

    for path, raw_post in _iter_markdown(docs_dir / "sources"):
        post = _load_or_record_violation(path, raw_post, result.violations, docs_dir)
        if post is None:
            continue
        rel_path = str(path.relative_to(docs_dir.parent))

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
    manifest = SourceManifest(docs_dir / SOURCE_MANIFEST_FILENAME)
    catalog = read_jsonl(docs_dir / "catalog.jsonl")

    covering_notes: dict[str, set[str]] = {}
    for entry in catalog:
        for source_id in entry.get("sources") or []:
            covering_notes.setdefault(source_id, set()).add(entry.get("path", ""))

    result = SourceCoverageResult()
    seen: set[str] = set()
    for path, raw_post in _iter_markdown(docs_dir / "sources"):
        post = _load_or_record_violation(path, raw_post, result.violations, docs_dir)
        if post is None:
            continue
        rel_path = str(path.relative_to(docs_dir.parent))

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


BOOKKEEPING_FIELDS = {"processed", "duplicate", "source"}


@dataclass
class Delta:
    """Result of diffing a source's current content against its last-known revision on `main`."""

    changed_fields: dict[str, tuple[Any, Any]] = field(default_factory=dict)


def diff_content_fields(old: dict, new: dict) -> dict[str, tuple[Any, Any]]:
    """Diff two frontmatter metadata dicts, excluding CLI bookkeeping fields (`processed`, `duplicate`, `source`).

    Returns `{field: (old_value, new_value)}` for every field that was added, removed, or changed.
    """
    keys = (set(old) | set(new)) - BOOKKEEPING_FIELDS
    changed = {}
    for key in keys:
        old_value = old.get(key)
        new_value = new.get(key)
        if old_value != new_value:
            changed[key] = (old_value, new_value)
    return changed


def last_known_revision(root: Path, rel_path: str) -> str | None:
    """Return `rel_path`'s content as of the last commit touching it on `main`, or None if never committed there."""
    git = shutil.which("git")
    if git is None:
        return None
    try:
        log_result = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
            [git, "log", "-1", "--format=%H", "main", "--", rel_path],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError:
        return None
    sha = log_result.stdout.strip()
    if not sha:
        return None
    try:
        show_result = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
            [git, "show", f"{sha}:{rel_path}"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError:
        return None
    return show_result.stdout


def compute_source_delta(docs_dir: Path, source: str) -> Delta:
    """Diff a source's current working-tree content against its last-known revision on `main`.

    Resolves the source's path via `source-manifest.jsonl`. A source with no prior
    commit on `main` diffs against a synthetic empty baseline (every field reports
    as new) rather than erroring.
    """
    manifest = SourceManifest(docs_dir / SOURCE_MANIFEST_FILENAME)
    entry = _resolve_source_entry(manifest, source)

    root = docs_dir.parent
    rel_path = entry["path"]
    current_post = Post.loads((root / rel_path).read_text(encoding="utf-8"))

    old_text = last_known_revision(root, rel_path)
    old_metadata = Post.loads(old_text).metadata if old_text is not None else {}

    return Delta(changed_fields=diff_content_fields(old_metadata, current_post.metadata))


@dataclass
class DedupeCandidate:
    """One file within a duplicate group."""

    path: str
    mtime: float
    similarity: float  # difflib ratio against the suggested keeper; 1.0 for the keeper itself


@dataclass
class DedupeGroup:
    """All `docs/sources/` files sharing a `source` id, where at least one is flagged `duplicate: true`."""

    source: str
    keep: str  # path suggested to keep
    reason: str
    candidates: list[DedupeCandidate] = field(default_factory=list)


@dataclass
class DedupeResult:
    """The full result of a `source-dedupe` pass."""

    groups: list[DedupeGroup] = field(default_factory=list)
    violations: list[LintViolation] = field(default_factory=list)

    @property
    def needs_attention(self) -> bool:
        """True if any duplicate group was found."""
        return bool(self.groups)


def suggest_dedupe(docs_dir: Path) -> DedupeResult:
    """Group `docs_dir/sources/` files by shared `source` id and suggest which to keep.

    A group is included only for `source` ids with at least one `duplicate: true`
    file *and* more than one file sharing the id (a lone `duplicate: true` file
    with no sibling has nothing to compare against). The suggested keeper is the
    file with the latest mtime; content-similarity scores (difflib ratio against
    the keeper) are reported per candidate so a human can confirm the call. Never
    modifies or deletes files — suggestion only. A file with malformed frontmatter
    is reported as a violation instead of raising.
    """
    result = DedupeResult()

    groups: dict[str, list[Path]] = {}
    flagged: set[str] = set()
    for path, raw_post in _iter_markdown(docs_dir / "sources"):
        post = _load_or_record_violation(path, raw_post, result.violations, docs_dir)
        if post is None:
            continue

        source_id = post.get("source")
        if not source_id:
            continue
        groups.setdefault(source_id, []).append(path)
        if post.get("duplicate"):
            flagged.add(source_id)

    for source_id in sorted(flagged):
        group_paths = groups[source_id]
        if len(group_paths) < 2:
            continue

        contents = {p: p.read_text(encoding="utf-8") for p in group_paths}
        keeper = max(group_paths, key=lambda p: p.stat().st_mtime)
        keeper_content = contents[keeper]

        candidates = [
            DedupeCandidate(
                path=str(p.relative_to(docs_dir.parent)),
                mtime=p.stat().st_mtime,
                similarity=1.0 if p == keeper else SequenceMatcher(None, keeper_content, contents[p]).ratio(),
            )
            for p in group_paths
        ]
        result.groups.append(
            DedupeGroup(
                source=source_id,
                keep=str(keeper.relative_to(docs_dir.parent)),
                reason="most recently modified",
                candidates=candidates,
            )
        )

    return result


SnapshotUnits = Literal["comments", "fields"]
ALLOWED_SNAPSHOT_UNITS: tuple[SnapshotUnits, ...] = ("comments", "fields")


@dataclass
class SnapshotResult:
    """Result of writing a new Raw snapshot unit for a source."""

    source: str
    path: str
    units: SnapshotUnits
    update_sha: str


def write_source_snapshot(
    docs_dir: Path, source: str, units: str, *, stage_root: Path | None = None
) -> SnapshotResult:
    """Write a new Raw snapshot unit for `source`, for the given mutation type (`comments` or `fields`).

    Resolves the source's path via `source-manifest.jsonl`, resets `processed: false` on the
    file — the existing reprocessing signal (see `apply_source_scan`) — and records the current
    on-disk content's hash and timestamp as the manifest's new `update_sha`/`updated`, giving an
    explicit, versioned record of this mutation (the "computed SHA hash of files for mutable
    sources" case the manifest's `update_sha` field already covers). Works entirely against
    content already materialized on disk; v1 has no live adapter fetch to populate `units:
    comments` from, so `units` is a bookkeeping distinction for downstream PR framing, not a
    different write.
    """
    if units not in ALLOWED_SNAPSHOT_UNITS:
        raise ValueError(f"invalid units {units!r}; must be one of {ALLOWED_SNAPSHOT_UNITS}")

    manifest = SourceManifest(docs_dir / SOURCE_MANIFEST_FILENAME)
    entry = _resolve_source_entry(manifest, source)

    rel_path = entry["path"]
    source_path = docs_dir.parent / rel_path
    _stamp_frontmatter(source_path, processed=False, stage_root=stage_root)

    now = datetime.now(UTC).isoformat()
    update_sha = hashlib.sha256(source_path.read_bytes()).hexdigest()
    manifest[source] = {**entry, "updated": now, "update_sha": update_sha}
    manifest.save(stage_root=stage_root)
    return SnapshotResult(source=source, path=rel_path, units=units, update_sha=update_sha)  # type: ignore[arg-type]
