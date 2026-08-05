"""Unit tests for wiki_toolkit.sources's internal (non-Click) logic."""

from typing import TYPE_CHECKING

import orjson

from wiki_toolkit.sources import apply_source_scan, lint_sources, scan_sources, source_coverage

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


def test_lint_sources_flags_missing_source_field(make_docs_tree: Callable[[], Path]) -> None:
    """A source file with no `source` frontmatter field is flagged."""
    docs_dir = make_docs_tree()
    (docs_dir / "sources" / "a.md").write_text("---\ntitle: no source id\n---\nbody")

    result = lint_sources(docs_dir)

    assert len(result.violations) == 1
    assert "missing required `source` field" in result.violations[0].message
    assert result.ok is False


def test_lint_sources_flags_invalid_processed_value(make_docs_tree: Callable[[], Path], make_source) -> None:
    """A `processed` field that isn't a boolean is flagged."""
    docs_dir = make_docs_tree()
    make_source(docs_dir, "jira:ABC-1", processed="yes")

    result = lint_sources(docs_dir)

    assert len(result.violations) == 1
    assert "`processed` must be a boolean" in result.violations[0].message


def test_lint_sources_flags_invalid_duplicate_value(make_docs_tree: Callable[[], Path], make_source) -> None:
    """A `duplicate` field that isn't a boolean is flagged."""
    docs_dir = make_docs_tree()
    make_source(docs_dir, "jira:ABC-1", duplicate="nope")

    result = lint_sources(docs_dir)

    assert len(result.violations) == 1
    assert "`duplicate` must be a boolean" in result.violations[0].message


def test_lint_sources_reports_processed_uncovered_as_backlog_not_violation(
    make_docs_tree: Callable[[], Path], make_source
) -> None:
    """A `processed` source with no `covered_by` entry is a backlog item, not a hard error."""
    docs_dir = make_docs_tree()
    (docs_dir / "source-manifest.jsonl").write_text(orjson.dumps({"source": "jira:ABC-1"}).decode() + "\n")
    make_source(docs_dir, "jira:ABC-1", processed=True)

    result = lint_sources(docs_dir)

    assert result.violations == []
    assert result.backlog == ["jira:ABC-1"]
    assert result.ok is True


def test_lint_sources_covered_source_not_in_backlog(make_docs_tree: Callable[[], Path], make_source) -> None:
    """A `processed` source that already has a `covered_by` entry is not in the backlog."""
    docs_dir = make_docs_tree()
    manifest_entry = {"source": "jira:ABC-1", "covered_by": ["docs/wiki/foo.md"]}
    (docs_dir / "source-manifest.jsonl").write_text(orjson.dumps(manifest_entry).decode() + "\n")
    make_source(docs_dir, "jira:ABC-1", processed=True)

    result = lint_sources(docs_dir)

    assert result.backlog == []


def test_lint_sources_clean_tree_has_no_violations_or_backlog(make_docs_tree: Callable[[], Path], make_source) -> None:
    """A well-formed, unprocessed source passes clean with no backlog entries."""
    docs_dir = make_docs_tree()
    make_source(docs_dir, "jira:ABC-1")

    result = lint_sources(docs_dir)

    assert result.violations == []
    assert result.backlog == []
    assert result.ok is True


def test_lint_sources_flags_malformed_frontmatter(make_docs_tree: Callable[[], Path]) -> None:
    """A source file with unparsable YAML frontmatter is flagged, not raised."""
    docs_dir = make_docs_tree()
    (docs_dir / "sources" / "bad.md").write_text("---\nsource: [unclosed\n---\nbody")

    result = lint_sources(docs_dir)

    assert len(result.violations) == 1
    assert "malformed frontmatter" in result.violations[0].message
    assert result.ok is False


def test_source_coverage_covered_via_catalog_sources(make_docs_tree: Callable[[], Path], make_source) -> None:
    """A source referenced by a wiki note's `sources` list is reported covered."""
    docs_dir = make_docs_tree()
    (docs_dir / "source-manifest.jsonl").write_text("")
    make_source(docs_dir, "jira:ABC-1")
    entry = {"path": "docs/wiki/foo.md", "sources": ["jira:ABC-1"]}
    (docs_dir / "catalog.jsonl").write_text(orjson.dumps(entry).decode() + "\n")

    result = source_coverage(docs_dir)

    assert len(result.entries) == 1
    assert result.entries[0].covered is True
    assert result.entries[0].covered_by == ["docs/wiki/foo.md"]
    assert result.covered == result.entries
    assert result.uncovered == []


def test_source_coverage_covered_via_manifest_covered_by(make_docs_tree: Callable[[], Path], make_source) -> None:
    """A source with a manifest `covered_by` entry is reported covered even absent a catalog entry."""
    docs_dir = make_docs_tree()
    manifest_entry = {"source": "jira:ABC-1", "covered_by": ["docs/wiki/foo.md"]}
    (docs_dir / "source-manifest.jsonl").write_text(orjson.dumps(manifest_entry).decode() + "\n")
    (docs_dir / "catalog.jsonl").write_text("")
    make_source(docs_dir, "jira:ABC-1")

    result = source_coverage(docs_dir)

    assert result.entries[0].covered is True


def test_source_coverage_uncovered_source(make_docs_tree: Callable[[], Path], make_source) -> None:
    """A source with no covering wiki note is reported uncovered."""
    docs_dir = make_docs_tree()
    (docs_dir / "source-manifest.jsonl").write_text("")
    (docs_dir / "catalog.jsonl").write_text("")
    make_source(docs_dir, "jira:ABC-1")

    result = source_coverage(docs_dir)

    assert result.entries[0].covered is False
    assert result.uncovered == result.entries
    assert result.covered == []


def test_source_coverage_excludes_duplicate_flagged_sources(make_docs_tree: Callable[[], Path], make_source) -> None:
    """A duplicate-flagged source is excluded from the coverage report, consistent with source-scan."""
    docs_dir = make_docs_tree()
    (docs_dir / "source-manifest.jsonl").write_text("")
    (docs_dir / "catalog.jsonl").write_text("")
    make_source(docs_dir, "jira:ABC-1", duplicate=True)

    result = source_coverage(docs_dir)

    assert result.entries == []


def test_source_coverage_excludes_in_pass_duplicate_not_yet_stamped(
    make_docs_tree: Callable[[], Path], make_source
) -> None:
    """A later file sharing a source id already seen in this pass is excluded, even unstamped."""
    docs_dir = make_docs_tree()
    (docs_dir / "source-manifest.jsonl").write_text("")
    (docs_dir / "catalog.jsonl").write_text("")
    make_source(docs_dir, "jira:ABC-1", filename="a-first.md")
    make_source(docs_dir, "jira:ABC-1", filename="b-second.md")

    result = source_coverage(docs_dir)

    assert [e.path.split("/")[-1] for e in result.entries] == ["a-first.md"]


def test_source_coverage_skips_version_controlled_sources(make_docs_tree: Callable[[], Path], make_source) -> None:
    """Version-controlled sources are skipped, consistent with scan_sources."""
    docs_dir = make_docs_tree()
    (docs_dir / "source-manifest.jsonl").write_text("")
    (docs_dir / "catalog.jsonl").write_text("")
    make_source(docs_dir, "github:repo@sha", kind="version_controlled")

    result = source_coverage(docs_dir)

    assert result.entries == []


def test_source_coverage_flags_malformed_frontmatter(make_docs_tree: Callable[[], Path]) -> None:
    """A source file with unparsable YAML frontmatter is flagged, not raised."""
    docs_dir = make_docs_tree()
    (docs_dir / "source-manifest.jsonl").write_text("")
    (docs_dir / "catalog.jsonl").write_text("")
    (docs_dir / "sources" / "bad.md").write_text("---\nsource: [unclosed\n---\nbody")

    result = source_coverage(docs_dir)

    assert result.entries == []
    assert len(result.violations) == 1
    assert "malformed frontmatter" in result.violations[0].message
    assert result.violations[0].path == "docs/sources/bad.md"
