"""Business logic for wiki_toolkit, independent of the Click CLI adapter."""

import hashlib
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import UTC, datetime
from difflib import SequenceMatcher
from typing import TYPE_CHECKING, Literal

import frontmatter
import yaml

from wiki_toolkit._io import write_jsonl
from wiki_toolkit.sources import SOURCE_MANIFEST_FILENAME, _read_manifest

if TYPE_CHECKING:
    from pathlib import Path


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


BOOKKEEPING_FIELDS = {"processed", "duplicate", "source"}


@dataclass
class Delta:
    """Result of diffing a source's current content against its last-known revision on `main`."""

    new_comment_ids: list[str] = field(default_factory=list)
    changed_fields: dict[str, tuple[object, object]] = field(default_factory=dict)


def diff_content_fields(old: dict, new: dict) -> dict[str, tuple[object, object]]:
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
    manifest = _read_manifest(docs_dir / SOURCE_MANIFEST_FILENAME)
    entry = manifest.get(source)
    if entry is None:
        raise ValueError(f"unknown source: {source!r}")

    root = docs_dir.parent
    rel_path = entry["path"]
    current_post = frontmatter.loads((root / rel_path).read_text(encoding="utf-8"))

    old_text = last_known_revision(root, rel_path)
    old_metadata = frontmatter.loads(old_text).metadata if old_text is not None else {}

    return Delta(changed_fields=diff_content_fields(old_metadata, current_post.metadata))


def search_catalog(query: str, entries: list[dict]) -> list[dict]:
    """Return catalog entries whose title or path contains `query`, case-insensitively."""
    needle = query.lower()
    return [e for e in entries if needle in e.get("title", "").lower() or needle in e.get("path", "").lower()]


def _stamp_frontmatter(path: Path, **fields: object) -> None:
    """Merge `fields` into a source file's frontmatter and write it back."""
    post = frontmatter.loads(path.read_text(encoding="utf-8"))
    for key, value in fields.items():
        post[key] = value
    path.write_bytes(frontmatter.dumps(post).encode())


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
    modifies or deletes files — suggestion only.
    """
    sources_dir = docs_dir / "sources"
    paths = sorted(sources_dir.rglob("*.md")) if sources_dir.is_dir() else []

    groups: dict[str, list[Path]] = {}
    flagged: set[str] = set()
    for path in paths:
        post = frontmatter.loads(path.read_text(encoding="utf-8"))
        source_id = post.get("source")
        if not source_id:
            continue
        groups.setdefault(source_id, []).append(path)
        if post.get("duplicate"):
            flagged.add(source_id)

    result = DedupeResult()
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


def write_source_snapshot(docs_dir: Path, source: str, units: str) -> SnapshotResult:
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

    manifest = _read_manifest(docs_dir / SOURCE_MANIFEST_FILENAME)
    entry = manifest.get(source)
    if entry is None:
        raise ValueError(f"unknown source: {source!r}")

    rel_path = entry["path"]
    source_path = docs_dir.parent / rel_path
    _stamp_frontmatter(source_path, processed=False)

    now = datetime.now(UTC).isoformat()
    update_sha = hashlib.sha256(source_path.read_bytes()).hexdigest()
    manifest[source] = {**entry, "updated": now, "update_sha": update_sha}
    write_jsonl(docs_dir / SOURCE_MANIFEST_FILENAME, [manifest[key] for key in manifest])

    return SnapshotResult(source=source, path=rel_path, units=units, update_sha=update_sha)  # type: ignore[arg-type]
