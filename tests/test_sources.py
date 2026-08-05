"""Unit tests for wiki_toolkit.sources's internal (non-Click) logic."""

from typing import TYPE_CHECKING

import orjson

from wiki_toolkit.sources import apply_source_scan, scan_sources

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


def test_scan_classifies_unknown_source_as_new(make_docs_tree: Callable[[], Path], make_source) -> None:
    """A source with no manifest entry is classified `new`."""
    docs_dir = make_docs_tree()
    make_source(docs_dir, "jira:ABC-1")

    result = scan_sources(docs_dir)

    assert [(e.source, e.classification) for e in result.entries] == [("jira:ABC-1", "new")]


def test_scan_classifies_known_source_as_update(make_docs_tree: Callable[[], Path], make_source) -> None:
    """A source already present in the manifest is classified `update`."""
    docs_dir = make_docs_tree()
    (docs_dir / "source-manifest.jsonl").write_text(orjson.dumps({"source": "jira:ABC-1"}).decode() + "\n")
    make_source(docs_dir, "jira:ABC-1")

    result = scan_sources(docs_dir)

    assert [(e.source, e.classification) for e in result.entries] == [("jira:ABC-1", "update")]


def test_scan_flags_second_file_with_same_source_as_duplicate(make_docs_tree: Callable[[], Path], make_source) -> None:
    """First-seen file for a `source` id is canonical; a later file with the same id is a duplicate."""
    docs_dir = make_docs_tree()
    make_source(docs_dir, "jira:ABC-1", filename="a-first.md")
    make_source(docs_dir, "jira:ABC-1", filename="b-second.md")

    result = scan_sources(docs_dir)

    classifications = [(e.path.split("/")[-1], e.classification) for e in result.entries]
    assert classifications == [("a-first.md", "new"), ("b-second.md", "duplicate")]


def test_scan_keeps_previously_stamped_duplicate_excluded(make_docs_tree: Callable[[], Path], make_source) -> None:
    """A file already stamped `duplicate: true` stays classified `duplicate` regardless of scan order."""
    docs_dir = make_docs_tree()
    make_source(docs_dir, "jira:ABC-1", filename="a-first.md")
    make_source(docs_dir, "jira:ABC-1", filename="z-already-flagged.md", duplicate=True)

    result = scan_sources(docs_dir)

    classifications = {e.path.split("/")[-1]: e.classification for e in result.entries}
    assert classifications == {"a-first.md": "new", "z-already-flagged.md": "duplicate"}


def test_scan_skips_version_controlled_sources(make_docs_tree: Callable[[], Path], make_source) -> None:
    """Version-controlled sources are skipped, never flagged new/update/duplicate."""
    docs_dir = make_docs_tree()
    make_source(docs_dir, "github:repo@sha", kind="version_controlled")

    result = scan_sources(docs_dir)

    assert result.entries == []
    assert len(result.skipped) == 1


def test_scan_covered_update_needs_accept_covered(make_docs_tree: Callable[[], Path], make_source) -> None:
    """An update to a source already covered by a wiki note is not accepted without --accept-covered."""
    docs_dir = make_docs_tree()
    manifest_entry = {"source": "jira:ABC-1", "covered_by": ["docs/wiki/foo.md"]}
    (docs_dir / "source-manifest.jsonl").write_text(orjson.dumps(manifest_entry).decode() + "\n")
    make_source(docs_dir, "jira:ABC-1")

    default_result = scan_sources(docs_dir)
    accepted_result = scan_sources(docs_dir, accept_covered=True)

    assert default_result.entries[0].covered is True
    assert default_result.entries[0].accepted is False
    assert accepted_result.entries[0].accepted is True


def test_scan_flags_malformed_frontmatter(make_docs_tree: Callable[[], Path]) -> None:
    """A source file with unparsable YAML frontmatter is flagged, not raised."""
    docs_dir = make_docs_tree()
    (docs_dir / "sources" / "bad.md").write_text("---\nsource: [unclosed\n---\nbody")

    result = scan_sources(docs_dir)

    assert result.entries == []
    assert len(result.violations) == 1
    assert "malformed frontmatter" in result.violations[0].message
    assert result.violations[0].path == "docs/sources/bad.md"


def test_apply_source_scan_stamps_processed_and_writes_manifest(
    make_docs_tree: Callable[[], Path], make_source
) -> None:
    """--update stamps `processed: true` on the source file and writes its manifest entry."""
    docs_dir = make_docs_tree()
    (docs_dir / "source-manifest.jsonl").write_text("")
    path = make_source(docs_dir, "jira:ABC-1")

    result = scan_sources(docs_dir)
    written = apply_source_scan(docs_dir, result)

    assert written == 1
    assert "processed: true" in path.read_text(encoding="utf-8")
    manifest_lines = (docs_dir / "source-manifest.jsonl").read_text(encoding="utf-8").splitlines()
    manifest = [orjson.loads(line) for line in manifest_lines]
    assert len(manifest) == 1
    assert manifest[0]["source"] == "jira:ABC-1"
    assert manifest[0]["path"] == "docs/sources/jira-ABC-1.md"


def test_apply_source_scan_stamps_duplicate_without_touching_manifest(
    make_docs_tree: Callable[[], Path], make_source
) -> None:
    """--update stamps `duplicate: true` on later files, but does not give them their own manifest entry."""
    docs_dir = make_docs_tree()
    (docs_dir / "source-manifest.jsonl").write_text("")
    make_source(docs_dir, "jira:ABC-1", filename="a-first.md")
    dup_path = make_source(docs_dir, "jira:ABC-1", filename="b-second.md")

    result = scan_sources(docs_dir)
    apply_source_scan(docs_dir, result)

    assert "duplicate: true" in dup_path.read_text(encoding="utf-8")
    manifest_lines = (docs_dir / "source-manifest.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(manifest_lines) == 1
    assert orjson.loads(manifest_lines[0])["path"] == "docs/sources/a-first.md"


def test_apply_source_scan_skips_unaccepted_covered_update(make_docs_tree: Callable[[], Path], make_source) -> None:
    """An unaccepted covered update is neither stamped `processed` nor rewritten into the manifest."""
    docs_dir = make_docs_tree()
    manifest_entry = {"source": "jira:ABC-1", "path": "docs/sources/jira-ABC-1.md", "covered_by": ["docs/wiki/foo.md"]}
    (docs_dir / "source-manifest.jsonl").write_text(orjson.dumps(manifest_entry).decode() + "\n")
    path = make_source(docs_dir, "jira:ABC-1")

    result = scan_sources(docs_dir)
    written = apply_source_scan(docs_dir, result)

    assert written == 0
    assert "processed: true" not in path.read_text(encoding="utf-8")
