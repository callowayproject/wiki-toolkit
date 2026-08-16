"""Wiki-note catalog, lint, and search logic for wiki_toolkit."""

import re
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Literal

from wiki_toolkit._io import read_jsonl
from wiki_toolkit.frontmatter import Post
from wiki_toolkit.sources import SOURCE_MANIFEST_FILENAME, LintViolation, LoadError, SourceManifest, _iter_markdown

_BULLET_RE = re.compile(r"^\s*[-*]\s+(.*)$")
_WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]")
_CONFIDENCE_MARKER_RE = re.compile(r"\^\[(inferred|ambiguous)\]")
_CONFIDENCE_STATES = ("extracted", "inferred", "ambiguous")
_RELATIONSHIP_TYPES = frozenset(
    {"extends", "implements", "contradicts", "derived_from", "uses", "replaces", "related_to"}
)


@dataclass
class CatalogEntry:
    """A single `docs/wiki/` note's catalog entry."""

    path: str
    title: str
    updated: str
    sources: list[str]
    status: Literal["resolved", "proposed"]
    aliases: list[str] = field(default_factory=list)
    links: list[str] = field(default_factory=list)


@dataclass
class CatalogResult:
    """The full result of a `build` pass."""

    entries: list[CatalogEntry] = field(default_factory=list)
    violations: list[LintViolation] = field(default_factory=list)


def _extract_wikilinks(content: str) -> list[str]:
    """Return the deduplicated, ordered `[[target]]` (or `[[target|display]]`) targets in `content`.

    Strips any `#heading` or `^block-id` anchor from each target, and dedupes
    case-insensitively (keeping the first-seen casing) to match this module's
    other wikilink-target comparisons (see `known_targets` in `lint_wiki`).
    """
    seen: dict[str, str] = {}
    for match in _WIKILINK_RE.finditer(content):
        target = re.split(r"[#^]", match.group(1).strip(), maxsplit=1)[0].strip()
        seen.setdefault(target.lower(), target)
    return list(seen.values())


def build_catalog(docs_dir: Path) -> CatalogResult:
    """Walk `docs_dir/wiki/`, parsing frontmatter into a catalog entry per note.

    `status` is `resolved` iff every source the note references is `resolved`
    in the source manifest (vacuously true for a note with no sources), else
    `proposed`. A note with malformed frontmatter is reported as a violation
    instead of raising.
    """
    manifest = SourceManifest(docs_dir / SOURCE_MANIFEST_FILENAME)
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
                aliases=post.get("aliases") or [],
                links=_extract_wikilinks(post.content),
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


def _strip_wikilink(target: str) -> str:
    """Strip an optional `[[...]]` wrapper from a relationship `target` string."""
    target = target.strip()
    if target.startswith("[[") and target.endswith("]]"):
        return target[2:-2].strip()
    return target


def _check_relationships(post: Post, known_targets: set[str]) -> list[str]:
    """Return violation messages for `post`'s `relationships:` entries.

    Returns `[]` if `post` has no `relationships:` block (opt-in, unaffected by this
    check). Each entry's `type` must be one of `_RELATIONSHIP_TYPES`; each entry's
    `target` must resolve (by title or path, case-insensitively) against
    `known_targets`. Unresolved targets are flagged, not rejected.
    """
    relationships = post.get("relationships")
    if relationships is None:
        return []
    if not isinstance(relationships, list):
        return [f"`relationships` must be a list, got {relationships!r}"]
    messages: list[str] = []
    for entry in relationships:
        if not isinstance(entry, dict):
            messages.append(f"relationship entry must be a mapping, got {entry!r}")
            continue
        rel_type = entry.get("type")
        if rel_type not in _RELATIONSHIP_TYPES:
            messages.append(f"relationship type {rel_type!r} is not one of {sorted(_RELATIONSHIP_TYPES)}")
        target = entry.get("target") or ""
        if not isinstance(target, str):
            messages.append(f"relationship target must be a string, got {target!r}")
            continue
        if _strip_wikilink(target).lower() not in known_targets:
            messages.append(f"relationship target {target!r} does not resolve to an existing wiki page")
    return messages


def _check_tags_and_sources(post: Post, allowed_tags: set[str] | None, manifest: SourceManifest) -> list[str]:
    """Return violation messages for `post`'s `tags`, `sources`, and `source_count` fields."""
    messages: list[str] = []
    if allowed_tags is not None:
        messages.extend(f"disallowed tag: {tag!r}" for tag in post.get("tags") or [] if tag not in allowed_tags)

    sources = post.get("sources") or []
    messages.extend(
        f"unresolved source reference: {source_id!r}" for source_id in sources if source_id not in manifest
    )

    source_count = post.get("source_count")
    if source_count is not None and source_count != len(sources):
        messages.append(f"source_count is {source_count}, but sources list has {len(sources)}")

    return messages


def lint_wiki(docs_dir: Path) -> LintResult:
    """Validate every note in `docs_dir/wiki/`: frontmatter, tags, source links, `source_count`.

    Tags are checked against the taxonomy in `docs_dir/schema.md` (skipped if that file
    is absent). Sources are checked against `docs_dir/source-manifest.jsonl`.
    """
    result = LintResult()
    manifest = SourceManifest(docs_dir / SOURCE_MANIFEST_FILENAME)

    schema_path = docs_dir / "schema.md"
    allowed_tags = parse_tag_taxonomy(schema_path.read_text(encoding="utf-8")) if schema_path.is_file() else None

    entries = list(_iter_markdown(docs_dir / "wiki"))
    known_targets: set[str] = set()
    for path, post in entries:
        if isinstance(post, LoadError):
            continue
        known_targets.add((post.get("title") or path.stem).lower())
        known_targets.add(path.stem.lower())

    for path, post in entries:
        rel_path = str(path.relative_to(docs_dir.parent))

        if isinstance(post, LoadError):
            result.violations.append(LintViolation(rel_path, post.message))
            continue

        for tag_source_message in _check_tags_and_sources(post, allowed_tags, manifest):
            result.violations.append(LintViolation(rel_path, tag_source_message))

        confidence_message = _check_confidence_drift(post, post.content)
        if confidence_message is not None:
            result.violations.append(LintViolation(rel_path, confidence_message))

        for relationship_message in _check_relationships(post, known_targets):
            result.violations.append(LintViolation(rel_path, relationship_message))

    return result


def search_catalog(query: str, entries: list[dict]) -> list[dict]:
    """Return catalog entries whose title or path contains `query`, case-insensitively."""
    needle = query.lower()
    return [e for e in entries if needle in e.get("title", "").lower() or needle in e.get("path", "").lower()]


_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)


@dataclass
class CrossLinkCandidate:
    """A single literal-match cross-link candidate found in a session page's body."""

    page: str
    target: str
    mention_text: str
    match_type: Literal["title", "alias"]


def _protected_spans(content: str) -> list[tuple[int, int]]:
    """Return `(start, end)` spans in `content` that matches must not start inside: code blocks and `[[...]]`."""
    spans = [m.span() for m in _FENCE_RE.finditer(content)]
    spans.extend(m.span() for m in _WIKILINK_RE.finditer(content))
    return spans


def _build_cross_link_registry(
    catalog_entries: list[dict], own_pages: set[str]
) -> list[tuple[re.Pattern[str], str, Literal["title", "alias"]]]:
    """Return `(pattern, target_path, match_type)` triples for every catalog entry outside `own_pages`."""

    def compiled(match_string: str) -> re.Pattern[str]:
        return re.compile(rf"(?<!\w){re.escape(match_string)}(?!\w)", re.IGNORECASE)

    registry: list[tuple[re.Pattern[str], str, Literal["title", "alias"]]] = []
    for entry in catalog_entries:
        path = entry.get("path", "")
        if not path or path in own_pages:
            continue
        title = entry.get("title") or ""
        if title:
            registry.append((compiled(title), path, "title"))
        registry.extend((compiled(alias), path, "alias") for alias in entry.get("aliases") or [] if alias)
    return registry


def find_cross_link_candidates(docs_dir: Path, page_paths: list[str]) -> list[CrossLinkCandidate]:
    """Find literal title/alias mentions of other catalog pages inside `page_paths`' bodies.

    `page_paths` are the session's own pages (paths as stored in `catalog.jsonl`, relative to
    `docs_dir.parent`) — the only bodies read. Every other catalog entry is a potential match
    target, matched by `title` and `aliases`, never re-read as a source. A match inside a fenced
    code block or an existing `[[...]]` wikilink is skipped; at most one candidate is reported
    per `(page, target)` pair, preferring a `title` match over an `alias` match.
    """
    own_pages = set(page_paths)
    registry = _build_cross_link_registry(read_jsonl(docs_dir / "catalog.jsonl"), own_pages)

    candidates: list[CrossLinkCandidate] = []
    for page in page_paths:
        full_path = docs_dir.parent / page
        if not full_path.is_file():
            continue
        content = Post.loads(full_path.read_text(encoding="utf-8")).content
        spans = _protected_spans(content)

        matched_targets: set[str] = set()
        for pattern, target, match_type in registry:
            if target in matched_targets:
                continue
            match = next((m for m in pattern.finditer(content) if not _in_span(m.start(), spans)), None)
            if match is None:
                continue
            matched_targets.add(target)
            candidates.append(
                CrossLinkCandidate(page=page, target=target, mention_text=match.group(0), match_type=match_type)
            )

    return candidates


def _in_span(pos: int, spans: list[tuple[int, int]]) -> bool:
    """Report whether `pos` falls inside any `(start, end)` span."""
    return any(start <= pos < end for start, end in spans)
