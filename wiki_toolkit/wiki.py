"""Wiki-note catalog, lint, and search logic for wiki_toolkit."""

import re
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING, Literal

from wiki_toolkit.sources import SOURCE_MANIFEST_FILENAME, LintViolation, LoadError, _iter_markdown, _read_manifest

if TYPE_CHECKING:
    from pathlib import Path

    from wiki_toolkit.frontmatter import Post

_BULLET_RE = re.compile(r"^\s*[-*]\s+(.*)$")
_CONFIDENCE_MARKER_RE = re.compile(r"\^\[(inferred|ambiguous)\]")
_CONFIDENCE_STATES = ("extracted", "inferred", "ambiguous")


@dataclass
class CatalogEntry:
    """A single `docs/wiki/` note's catalog entry."""

    path: str
    title: str
    updated: str
    sources: list[str]
    status: Literal["resolved", "proposed"]


@dataclass
class CatalogResult:
    """The full result of a `build` pass."""

    entries: list[CatalogEntry] = field(default_factory=list)
    violations: list[LintViolation] = field(default_factory=list)


def build_catalog(docs_dir: Path) -> CatalogResult:
    """Walk `docs_dir/wiki/`, parsing frontmatter into a catalog entry per note.

    `status` is `resolved` iff every source the note references is `resolved`
    in the source manifest (vacuously true for a note with no sources), else
    `proposed`. A note with malformed frontmatter is reported as a violation
    instead of raising.
    """
    manifest = _read_manifest(docs_dir / SOURCE_MANIFEST_FILENAME)
    result = CatalogResult()

    for path, post in _iter_markdown(docs_dir / "wiki"):
        rel_path = str(path.relative_to(docs_dir.parent))

        if isinstance(post, LoadError):
            result.violations.append(LintViolation(rel_path, post.message))
            continue

        sources = post.get("sources") or []
        resolved = all(manifest.get(source_id, {}).get("status") == "resolved" for source_id in sources)

        result.entries.append(
            CatalogEntry(
                path=rel_path,
                title=post.get("title") or path.stem,
                updated=post.get("updated", ""),
                sources=sources,
                status="resolved" if resolved else "proposed",
            )
        )

    return result


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


def _confidence_claim_units(content: str) -> list[str]:
    """Split a note body into countable claim units: bullets if any exist, else paragraphs.

    One unit per bullet line (`- ` or `* `) when the body has any; otherwise one unit
    per blank-line-separated paragraph.
    """
    bullets = [m.group(1) for line in content.splitlines() if (m := _BULLET_RE.match(line))]
    if bullets:
        return bullets
    return [para for para in re.split(r"\n\s*\n", content) if para.strip()]


def _round_half_up(value: float, ndigits: int = 2) -> float:
    """Round `value` to `ndigits` decimal places, ties rounding away from zero."""
    quantum = Decimal(1).scaleb(-ndigits)
    return float(Decimal(str(value)).quantize(quantum, rounding=ROUND_HALF_UP))


def _recompute_confidence(content: str) -> dict[str, float]:
    """Recompute the `extracted`/`inferred`/`ambiguous` fraction rollup from a note's body.

    Each claim unit (see `_confidence_claim_units`) is `inferred` or `ambiguous` if it
    carries that `^[marker]`, else `extracted`. Fractions are rounded to 2 decimal
    places, round-half-up. A body with no claim units rolls up to all zeros.
    """
    units = _confidence_claim_units(content)
    counts: dict[str, int] = dict.fromkeys(_CONFIDENCE_STATES, 0)
    for unit in units:
        match = _CONFIDENCE_MARKER_RE.search(unit)
        state: str = match.group(1) if match else "extracted"
        counts[state] += 1

    total = len(units)
    if total == 0:
        return dict.fromkeys(_CONFIDENCE_STATES, 0.0)
    return {state: _round_half_up(counts[state] / total) for state in _CONFIDENCE_STATES}


def _check_confidence_drift(post: Post, content: str) -> str | None:
    """Return a violation message if `post`'s `confidence:` block doesn't match its recomputed markers.

    Returns `None` if `post` has no `confidence:` block (opt-in, unaffected by this check) or
    if the block matches. `content` is the note body the markers are recomputed from.
    """
    confidence = post.get("confidence")
    if confidence is None:
        return None
    if not isinstance(confidence, dict):
        return f"`confidence` must be a mapping, got {confidence!r}"
    recomputed = _recompute_confidence(content)
    if any(confidence.get(state) != recomputed[state] for state in _CONFIDENCE_STATES):
        return f"confidence is {confidence}, but recomputed markers give {recomputed}"
    return None


def lint_wiki(docs_dir: Path) -> LintResult:
    """Validate every note in `docs_dir/wiki/`: frontmatter, tags, source links, `source_count`.

    Tags are checked against the taxonomy in `docs_dir/schema.md` (skipped if that file
    is absent). Sources are checked against `docs_dir/source-manifest.jsonl`.
    """
    result = LintResult()
    manifest = _read_manifest(docs_dir / SOURCE_MANIFEST_FILENAME)

    schema_path = docs_dir / "schema.md"
    allowed_tags = parse_tag_taxonomy(schema_path.read_text(encoding="utf-8")) if schema_path.is_file() else None

    for path, post in _iter_markdown(docs_dir / "wiki"):
        rel_path = str(path.relative_to(docs_dir.parent))

        if isinstance(post, LoadError):
            result.violations.append(LintViolation(rel_path, post.message))
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

        confidence_message = _check_confidence_drift(post, post.content)
        if confidence_message is not None:
            result.violations.append(LintViolation(rel_path, confidence_message))

    return result


def search_catalog(query: str, entries: list[dict]) -> list[dict]:
    """Return catalog entries whose title or path contains `query`, case-insensitively."""
    needle = query.lower()
    return [e for e in entries if needle in e.get("title", "").lower() or needle in e.get("path", "").lower()]
