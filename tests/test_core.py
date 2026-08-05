"""Unit tests for wiki_toolkit.core's internal (non-Click) logic."""

from typing import TYPE_CHECKING

import orjson

from wiki_toolkit._io import read_jsonl, write_jsonl
from wiki_toolkit.core import (
    build_catalog,
    lint_wiki,
    parse_tag_taxonomy,
    search_catalog,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


def test_build_catalog_entry_fields(make_docs_tree: Callable[[], Path], make_wiki_note) -> None:
    """Each note yields an entry with path, title, updated, and sources."""
    docs_dir = make_docs_tree()
    make_wiki_note(docs_dir, "a.md", title="A Page", updated="2026-01-01", sources=["jira:ABC-1"])

    entries = build_catalog(docs_dir)

    assert len(entries) == 1
    entry = entries[0]
    assert entry.path == "docs/wiki/a.md"
    assert entry.title == "A Page"
    assert entry.updated == "2026-01-01"
    assert entry.sources == ["jira:ABC-1"]


def test_build_catalog_falls_back_to_filename_for_missing_title(
    make_docs_tree: Callable[[], Path], make_wiki_note
) -> None:
    """A note without a `title` field falls back to its filename stem."""
    docs_dir = make_docs_tree()
    make_wiki_note(docs_dir, "untitled.md")

    entries = build_catalog(docs_dir)

    assert entries[0].title == "untitled"


def test_build_catalog_status_resolved_when_all_sources_resolved(
    make_docs_tree: Callable[[], Path], make_wiki_note
) -> None:
    """A note is `resolved` when every referenced source is `resolved` in the manifest."""
    docs_dir = make_docs_tree()
    manifest_entry = {"source": "jira:ABC-1", "status": "resolved"}
    (docs_dir / "source-manifest.jsonl").write_text(orjson.dumps(manifest_entry).decode() + "\n")
    make_wiki_note(docs_dir, "a.md", sources=["jira:ABC-1"])

    entries = build_catalog(docs_dir)

    assert entries[0].status == "resolved"


def test_build_catalog_status_proposed_when_any_source_proposed(
    make_docs_tree: Callable[[], Path], make_wiki_note
) -> None:
    """A note is `proposed` if any referenced source is not `resolved` in the manifest."""
    docs_dir = make_docs_tree()
    manifest_lines = [
        orjson.dumps({"source": "jira:ABC-1", "status": "resolved"}).decode(),
        orjson.dumps({"source": "jira:ABC-2", "status": "proposed"}).decode(),
    ]
    (docs_dir / "source-manifest.jsonl").write_text("\n".join(manifest_lines) + "\n")
    make_wiki_note(docs_dir, "a.md", sources=["jira:ABC-1", "jira:ABC-2"])

    entries = build_catalog(docs_dir)

    assert entries[0].status == "proposed"


def test_build_catalog_status_proposed_when_source_missing_from_manifest(
    make_docs_tree: Callable[[], Path], make_wiki_note
) -> None:
    """A note referencing a source with no manifest entry at all is `proposed`."""
    docs_dir = make_docs_tree()
    (docs_dir / "source-manifest.jsonl").write_text("")
    make_wiki_note(docs_dir, "a.md", sources=["jira:ABC-1"])

    entries = build_catalog(docs_dir)

    assert entries[0].status == "proposed"


def test_build_catalog_note_with_no_sources_is_resolved(make_docs_tree: Callable[[], Path], make_wiki_note) -> None:
    """A note referencing no sources is trivially `resolved`."""
    docs_dir = make_docs_tree()
    make_wiki_note(docs_dir, "a.md")

    entries = build_catalog(docs_dir)

    assert entries[0].sources == []
    assert entries[0].status == "resolved"


def test_build_catalog_empty_wiki_dir(make_docs_tree: Callable[[], Path]) -> None:
    """An empty docs/wiki/ produces an empty catalog, nothing crashes."""
    docs_dir = make_docs_tree()

    assert build_catalog(docs_dir) == []


def test_parse_tag_taxonomy_reads_bullets_under_heading() -> None:
    """Bullet items between `## Tag Taxonomy` and the next heading are the allowed tags."""
    text = "# Wiki Schema\n\n## Tag Taxonomy\n\n- infra\n- security\n\n## Other Section\n\n- not-a-tag\n"

    assert parse_tag_taxonomy(text) == {"infra", "security"}


def test_parse_tag_taxonomy_missing_section_is_empty() -> None:
    """No `## Tag Taxonomy` heading means no allowed tags."""
    assert parse_tag_taxonomy("# Wiki Schema\n\nsome prose\n") == set()


def test_lint_flags_malformed_frontmatter(make_docs_tree: Callable[[], Path]) -> None:
    """A note with unparsable YAML frontmatter is flagged, not raised."""
    docs_dir = make_docs_tree()
    (docs_dir / "schema.md").write_text("## Tag Taxonomy\n\n- infra\n")
    (docs_dir / "wiki" / "bad.md").write_text("---\ntitle: [unclosed\n---\nbody")

    result = lint_wiki(docs_dir)

    assert len(result.violations) == 1
    assert "malformed frontmatter" in result.violations[0].message
    assert result.ok is False


def test_lint_flags_disallowed_tag(make_docs_tree: Callable[[], Path], make_wiki_note) -> None:
    """A tag not in the schema's Tag Taxonomy is flagged."""
    docs_dir = make_docs_tree()
    (docs_dir / "schema.md").write_text("## Tag Taxonomy\n\n- infra\n")
    make_wiki_note(docs_dir, "a.md", tags=["infra", "bogus"])

    result = lint_wiki(docs_dir)

    assert len(result.violations) == 1
    assert "bogus" in result.violations[0].message


def test_lint_flags_unresolved_source(make_docs_tree: Callable[[], Path], make_wiki_note) -> None:
    """A `sources:` entry with no matching source-manifest entry is flagged."""
    docs_dir = make_docs_tree()
    (docs_dir / "source-manifest.jsonl").write_text("")
    make_wiki_note(docs_dir, "a.md", sources=["jira:ABC-1"])

    result = lint_wiki(docs_dir)

    assert len(result.violations) == 1
    assert "jira:ABC-1" in result.violations[0].message


def test_lint_flags_mismatched_source_count(make_docs_tree: Callable[[], Path], make_wiki_note) -> None:
    """A `source_count` that doesn't match the length of `sources:` is flagged."""
    docs_dir = make_docs_tree()
    manifest_entry = orjson.dumps({"source": "jira:ABC-1"}).decode()
    (docs_dir / "source-manifest.jsonl").write_text(manifest_entry + "\n")
    make_wiki_note(docs_dir, "a.md", sources=["jira:ABC-1"], source_count=2)

    result = lint_wiki(docs_dir)

    assert len(result.violations) == 1
    assert "source_count" in result.violations[0].message


def test_lint_clean_note_has_no_violations(make_docs_tree: Callable[[], Path], make_wiki_note) -> None:
    """A well-formed note with valid tags, resolved sources, and correct source_count passes clean."""
    docs_dir = make_docs_tree()
    (docs_dir / "schema.md").write_text("## Tag Taxonomy\n\n- infra\n")
    manifest_entry = orjson.dumps({"source": "jira:ABC-1"}).decode()
    (docs_dir / "source-manifest.jsonl").write_text(manifest_entry + "\n")
    make_wiki_note(docs_dir, "a.md", tags=["infra"], sources=["jira:ABC-1"], source_count=1)

    result = lint_wiki(docs_dir)

    assert result.violations == []
    assert result.ok is True


def test_read_jsonl_missing_file_returns_empty(tmp_path: Path) -> None:
    """A missing JSONL file reads as an empty list, not an error."""
    assert read_jsonl(tmp_path / "missing.jsonl") == []


def test_read_jsonl_round_trips_write_jsonl(tmp_path: Path) -> None:
    """read_jsonl parses exactly what write_jsonl wrote."""
    path = tmp_path / "f.jsonl"
    records = [{"a": 1}, {"b": 2}]

    write_jsonl(path, records)

    assert read_jsonl(path) == records


def test_search_catalog_matches_title_case_insensitively() -> None:
    """A query matching part of an entry's title, in any case, is returned."""
    entries = [{"title": "Auth Middleware", "path": "docs/wiki/auth.md"}]

    assert search_catalog("auth", entries) == entries


def test_search_catalog_matches_path() -> None:
    """A query matching part of an entry's path is returned even if the title doesn't match."""
    entries = [{"title": "Overview", "path": "docs/wiki/billing/overview.md"}]

    assert search_catalog("billing", entries) == entries


def test_search_catalog_no_match_returns_empty_list() -> None:
    """A query with no matches returns an empty list, not an error."""
    entries = [{"title": "Auth Middleware", "path": "docs/wiki/auth.md"}]

    assert search_catalog("nonexistent", entries) == []
