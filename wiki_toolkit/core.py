"""Business logic for wiki_toolkit, independent of the Click CLI adapter."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

import frontmatter
import yaml

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


def search_catalog(query: str, entries: list[dict]) -> list[dict]:
    """Return catalog entries whose title or path contains `query`, case-insensitively."""
    needle = query.lower()
    return [e for e in entries if needle in e.get("title", "").lower() or needle in e.get("path", "").lower()]
