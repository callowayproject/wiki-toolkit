"""Unit tests for wiki_toolkit.core's internal (non-Click) logic."""

import shutil
import subprocess
from typing import TYPE_CHECKING

import orjson

from wiki_toolkit.core import (
    DOCS_STRUCTURE,
    apply_source_scan,
    build_catalog,
    check_shallow_clone,
    lint_wiki,
    parse_tag_taxonomy,
    run_doctor,
    scan_sources,
    validate_jsonl,
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
