"""Unit tests for wiki_toolkit.core's internal (non-Click) logic."""

import os
import shutil
import subprocess
import time
from typing import TYPE_CHECKING

import frontmatter
import orjson
import pytest

from wiki_toolkit.core import (
    DOCS_STRUCTURE,
    append_log_entry,
    apply_source_scan,
    build_catalog,
    build_log_entry,
    check_shallow_clone,
    compute_source_delta,
    diff_content_fields,
    lint_sources,
    lint_wiki,
    parse_tag_taxonomy,
    read_jsonl,
    run_doctor,
    scan_sources,
    search_catalog,
    source_coverage,
    suggest_dedupe,
    validate_jsonl,
    write_jsonl,
    write_source_snapshot,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

GIT = shutil.which("git") or "git"


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
        [GIT, *args], cwd=root, capture_output=True, text=True, check=True
    )


def test_run_doctor_reports_all_structure_present(tmp_path: Path, make_docs_tree: Callable[[], Path]) -> None:
    """A fully-scaffolded docs/ tree has no missing structure entries."""
    make_docs_tree()

    report = run_doctor(tmp_path)

    assert report.missing_structure == []
    assert set(report.present_structure) == set(DOCS_STRUCTURE)


def test_run_doctor_reports_missing_structure(tmp_path: Path) -> None:
    """Absent docs/ elements are reported by name, nothing crashes."""
    (tmp_path / "docs").mkdir()

    report = run_doctor(tmp_path)

    assert set(report.missing_structure) == set(DOCS_STRUCTURE)
    assert report.present_structure == []
    assert report.ok is False


def test_run_doctor_counts_wiki_notes(tmp_path: Path, make_docs_tree: Callable[[], Path]) -> None:
    """note_count reflects the number of markdown files under docs/wiki/."""
    docs_dir = make_docs_tree()
    (docs_dir / "wiki" / "a.md").write_text("# a")
    (docs_dir / "wiki" / "b.md").write_text("# b")

    report = run_doctor(tmp_path)

    assert report.note_count == 2


def test_run_doctor_flags_malformed_jsonl(tmp_path: Path, make_docs_tree: Callable[[], Path]) -> None:
    """Malformed lines in catalog.jsonl/source-manifest.jsonl are reported, not raised."""
    docs_dir = make_docs_tree()
    (docs_dir / "catalog.jsonl").write_text('{"path": "a.md"}\nnot json\n')

    report = run_doctor(tmp_path)

    assert "catalog.jsonl" in report.jsonl_errors
    assert "line 2" in report.jsonl_errors["catalog.jsonl"][0]
    assert report.ok is False


def test_validate_jsonl_skips_blank_lines(tmp_path: Path) -> None:
    """Blank lines are not treated as malformed."""
    path = tmp_path / "f.jsonl"
    path.write_text('{"a": 1}\n\n{"b": 2}\n')

    assert validate_jsonl(path) == []


def test_check_shallow_clone_none_when_not_a_repo(tmp_path: Path) -> None:
    """A non-git directory reports None (unknown), not an exception."""
    assert check_shallow_clone(tmp_path) is None


def test_check_shallow_clone_false_for_full_clone(tmp_path: Path) -> None:
    """A normal, fully-committed git repo is not shallow."""
    _git(tmp_path, "init")
    (tmp_path / "f.txt").write_text("x")
    _git(tmp_path, "add", "f.txt")
    _git(tmp_path, "-c", "user.email=t@t.com", "-c", "user.name=t", "commit", "-m", "init")

    assert check_shallow_clone(tmp_path) is False


def test_check_shallow_clone_true_for_depth_one_clone(tmp_path: Path) -> None:
    """A depth-1 clone of another repo is reported as shallow."""
    source = tmp_path / "source"
    source.mkdir()
    _git(source, "init")
    (source / "f.txt").write_text("x")
    _git(source, "add", "f.txt")
    _git(source, "-c", "user.email=t@t.com", "-c", "user.name=t", "commit", "-m", "init")

    clone = tmp_path / "clone"
    subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
        [GIT, "clone", "--no-local", "--depth", "1", str(source), str(clone)], capture_output=True, check=True
    )

    assert check_shallow_clone(clone) is True


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


def test_suggest_dedupe_ignores_sources_without_duplicates(make_docs_tree: Callable[[], Path], make_source) -> None:
    """A source id with only one file (no `duplicate: true`) yields no group."""
    docs_dir = make_docs_tree()
    make_source(docs_dir, "jira:ABC-1")

    result = suggest_dedupe(docs_dir)

    assert result.groups == []
    assert result.needs_attention is False


def test_suggest_dedupe_groups_by_source_and_suggests_latest_mtime(
    make_docs_tree: Callable[[], Path], make_source
) -> None:
    """A duplicate group includes every file sharing the source id; the newest mtime is the keep suggestion."""
    docs_dir = make_docs_tree()
    old_path = make_source(docs_dir, "jira:ABC-1", filename="a-first.md")
    new_path = make_source(docs_dir, "jira:ABC-1", filename="b-second.md", duplicate=True)
    os.utime(old_path, (time.time() - 100, time.time() - 100))

    result = suggest_dedupe(docs_dir)

    assert len(result.groups) == 1
    assert result.needs_attention is True
    group = result.groups[0]
    assert group.source == "jira:ABC-1"
    assert group.keep == str(new_path.relative_to(docs_dir.parent))
    candidate_paths = {c.path for c in group.candidates}
    assert candidate_paths == {str(old_path.relative_to(docs_dir.parent)), str(new_path.relative_to(docs_dir.parent))}


def test_suggest_dedupe_scores_content_similarity_against_keeper(
    make_docs_tree: Callable[[], Path], make_source
) -> None:
    """Non-keeper candidates get a difflib similarity ratio against the keeper's content; the keeper scores 1.0."""
    docs_dir = make_docs_tree()
    make_source(docs_dir, "jira:ABC-1", filename="a-first.md", title="Old title")
    make_source(docs_dir, "jira:ABC-1", filename="b-second.md", duplicate=True, title="Completely different")

    result = suggest_dedupe(docs_dir)

    group = result.groups[0]
    by_path = {c.path: c for c in group.candidates}
    assert by_path[group.keep].similarity == pytest.approx(1.0)
    other = next(c for c in group.candidates if c.path != group.keep)
    assert 0.0 <= other.similarity < 1.0


def test_suggest_dedupe_ignores_lone_duplicate_flagged_file(make_docs_tree: Callable[[], Path], make_source) -> None:
    """A `duplicate: true` file with no sibling sharing its source id has nothing to compare against."""
    docs_dir = make_docs_tree()
    make_source(docs_dir, "jira:ABC-1", duplicate=True)

    result = suggest_dedupe(docs_dir)

    assert result.groups == []


def test_suggest_dedupe_never_modifies_files(make_docs_tree: Callable[[], Path], make_source) -> None:
    """suggest_dedupe is read-only: it never stamps frontmatter or deletes files."""
    docs_dir = make_docs_tree()
    path_a = make_source(docs_dir, "jira:ABC-1", filename="a-first.md")
    path_b = make_source(docs_dir, "jira:ABC-1", filename="b-second.md", duplicate=True)
    before_a, before_b = path_a.read_text(encoding="utf-8"), path_b.read_text(encoding="utf-8")

    suggest_dedupe(docs_dir)

    assert path_a.read_text(encoding="utf-8") == before_a
    assert path_b.read_text(encoding="utf-8") == before_b


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


def test_build_log_entry_has_expected_fields() -> None:
    """A built log entry has date, action, message, and details."""
    entry = build_log_entry("ingest", "Ingested a source", "details here")

    assert entry.action == "ingest"
    assert entry.message == "Ingested a source"
    assert entry.details == "details here"
    assert entry.date


def test_build_log_entry_rejects_disallowed_action() -> None:
    """An action outside the allowed set raises ValueError rather than silently logging it."""
    try:
        build_log_entry("bogus", "msg", "details")
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for disallowed action")


def test_append_log_entry_appends_without_rewriting_existing_lines(tmp_path: Path) -> None:
    """Appending a new entry leaves prior entries untouched and in order."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    first = build_log_entry("create", "first", "d1")
    append_log_entry(docs_dir, first)

    second = build_log_entry("update", "second", "d2")
    append_log_entry(docs_dir, second)

    lines = (docs_dir / "log.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert orjson.loads(lines[0])["message"] == "first"
    assert orjson.loads(lines[1])["message"] == "second"


def test_diff_content_fields_reports_changed_added_removed() -> None:
    """diff_content_fields reports every field that changed, was added, or was removed."""
    old = {"status": "open", "assignee": "alice", "gone": "bye"}
    new = {"status": "closed", "assignee": "alice", "fresh": "hi"}

    changed = diff_content_fields(old, new)

    assert changed == {
        "status": ("open", "closed"),
        "gone": ("bye", None),
        "fresh": (None, "hi"),
    }


def test_diff_content_fields_excludes_bookkeeping_fields() -> None:
    """processed/duplicate/source never appear in the diff, even when they differ."""
    old = {"source": "jira:ABC-1", "processed": False, "duplicate": False, "status": "open"}
    new = {"source": "jira:ABC-1", "processed": True, "duplicate": True, "status": "open"}

    changed = diff_content_fields(old, new)

    assert changed == {}


def _make_delta_repo(tmp_path: Path, make_docs_tree, make_source) -> Path:
    """Build a docs/ tree in a real git repo, with a source committed as the last-known revision on main."""
    docs_dir = make_docs_tree()
    make_source(docs_dir, "jira:ABC-1", filename="abc-1.md", status="open", assignee="alice")
    (docs_dir / "source-manifest.jsonl").write_text(
        orjson.dumps({"source": "jira:ABC-1", "path": "docs/sources/abc-1.md"}).decode() + "\n"
    )

    _git(tmp_path, "init", "-b", "main")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "-c", "user.email=t@t.com", "-c", "user.name=t", "commit", "-m", "init")

    return docs_dir


def test_compute_source_delta_reports_changed_field(
    tmp_path: Path, make_docs_tree: Callable[[], Path], make_source
) -> None:
    """A field changed on disk since the last commit on main shows up in changed_fields."""
    docs_dir = _make_delta_repo(tmp_path, make_docs_tree, make_source)
    make_source(docs_dir, "jira:ABC-1", filename="abc-1.md", status="closed", assignee="alice")

    delta = compute_source_delta(docs_dir, "jira:ABC-1")

    assert delta.changed_fields == {"status": ("open", "closed")}
    assert delta.new_comment_ids == []


def test_compute_source_delta_no_prior_commit_reports_every_field_as_new(
    tmp_path: Path, make_docs_tree: Callable[[], Path], make_source
) -> None:
    """A source never committed on main diffs against a synthetic empty baseline, not an error."""
    docs_dir = make_docs_tree()
    make_source(docs_dir, "jira:NEW-1", filename="new-1.md", status="open")
    (docs_dir / "source-manifest.jsonl").write_text(
        orjson.dumps({"source": "jira:NEW-1", "path": "docs/sources/new-1.md"}).decode() + "\n"
    )
    _git(tmp_path, "init", "-b", "main")

    delta = compute_source_delta(docs_dir, "jira:NEW-1")

    assert delta.changed_fields == {"status": (None, "open")}


def test_compute_source_delta_unknown_source_raises(make_docs_tree: Callable[[], Path]) -> None:
    """A source id with no manifest entry raises rather than silently diffing nothing."""
    docs_dir = make_docs_tree()

    try:
        compute_source_delta(docs_dir, "jira:MISSING")
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for unknown source")


def test_compute_source_delta_works_against_a_shallow_clone(tmp_path: Path, make_source) -> None:
    """A depth-1 clone still resolves a normal delta when the last-touching commit is the fetched tip.

    `doctor` warns operators to avoid shallow clones because a commit older
    than the fetch depth is unreachable; this test covers the shape of repo
    `source-delta` actually sees in that situation, per the acceptance
    criteria's "shallow-clone case."
    """
    source_root = tmp_path / "source"
    source_root.mkdir()
    docs_dir = source_root / "docs"
    (docs_dir / "sources").mkdir(parents=True)
    (source_root / "unrelated.txt").write_text("x")
    _git(source_root, "init", "-b", "main")
    _git(source_root, "add", "unrelated.txt")
    _git(source_root, "-c", "user.email=t@t.com", "-c", "user.name=t", "commit", "-m", "unrelated")

    make_source(docs_dir, "jira:ABC-1", filename="abc-1.md", status="open")
    (docs_dir / "source-manifest.jsonl").write_text(
        orjson.dumps({"source": "jira:ABC-1", "path": "docs/sources/abc-1.md"}).decode() + "\n"
    )
    _git(source_root, "add", ".")
    _git(source_root, "-c", "user.email=t@t.com", "-c", "user.name=t", "commit", "-m", "add source")

    clone_root = tmp_path / "clone"
    subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
        [GIT, "clone", "--no-local", "--depth", "1", str(source_root), str(clone_root)],
        capture_output=True,
        check=True,
    )
    (clone_root / "docs" / "sources" / "abc-1.md").write_text(
        (clone_root / "docs" / "sources" / "abc-1.md").read_text().replace("open", "closed")
    )

    delta = compute_source_delta(clone_root / "docs", "jira:ABC-1")

    assert delta.changed_fields == {"status": ("open", "closed")}


def test_write_source_snapshot_fields_resets_processed_and_stamps_manifest(
    make_docs_tree: Callable[[], Path], make_source
) -> None:
    """--units fields resets `processed` and records a fresh update_sha/updated in the manifest."""
    docs_dir = make_docs_tree()
    make_source(docs_dir, "jira:ABC-1", filename="abc-1.md", processed=True, status="closed")
    manifest_entry = {
        "source": "jira:ABC-1",
        "path": "docs/sources/abc-1.md",
        "updated": "2020-01-01T00:00:00",
        "update_sha": "",
    }
    (docs_dir / "source-manifest.jsonl").write_text(orjson.dumps(manifest_entry).decode() + "\n")

    result = write_source_snapshot(docs_dir, "jira:ABC-1", "fields")

    assert result.source == "jira:ABC-1"
    assert result.path == "docs/sources/abc-1.md"
    assert result.units == "fields"
    assert result.update_sha

    post = frontmatter.loads((docs_dir / "sources" / "abc-1.md").read_text(encoding="utf-8"))
    assert post["processed"] is False
    assert post["status"] == "closed"

    manifest_entry = orjson.loads((docs_dir / "source-manifest.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert manifest_entry["update_sha"] == result.update_sha
    assert manifest_entry["updated"] != "2020-01-01T00:00:00"


def test_write_source_snapshot_comments_writes_against_materialized_content(
    make_docs_tree: Callable[[], Path], make_source
) -> None:
    """--units comments performs the same write against a pre-materialized comment file, no live fetch needed."""
    docs_dir = make_docs_tree()
    make_source(docs_dir, "jira:ABC-1#c1", filename="abc-1-c1.md", processed=True, body="a new comment")
    (docs_dir / "source-manifest.jsonl").write_text(
        orjson.dumps({"source": "jira:ABC-1#c1", "path": "docs/sources/abc-1-c1.md"}).decode() + "\n"
    )

    result = write_source_snapshot(docs_dir, "jira:ABC-1#c1", "comments")

    assert result.units == "comments"
    assert result.update_sha
    post = frontmatter.loads((docs_dir / "sources" / "abc-1-c1.md").read_text(encoding="utf-8"))
    assert post["processed"] is False
    assert post["body"] == "a new comment"


def test_write_source_snapshot_unknown_source_raises(make_docs_tree: Callable[[], Path]) -> None:
    """A source id with no manifest entry raises rather than silently writing nothing."""
    docs_dir = make_docs_tree()

    try:
        write_source_snapshot(docs_dir, "jira:MISSING", "fields")
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for unknown source")


def test_write_source_snapshot_invalid_units_raises(make_docs_tree: Callable[[], Path], make_source) -> None:
    """An invalid --units value raises rather than silently writing something wrong."""
    docs_dir = make_docs_tree()
    make_source(docs_dir, "jira:ABC-1", filename="abc-1.md")
    (docs_dir / "source-manifest.jsonl").write_text(
        orjson.dumps({"source": "jira:ABC-1", "path": "docs/sources/abc-1.md"}).decode() + "\n"
    )

    try:
        write_source_snapshot(docs_dir, "jira:ABC-1", "bogus")
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for invalid units")
