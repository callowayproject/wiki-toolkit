"""Unit tests for wiki_toolkit.init."""

from typing import TYPE_CHECKING

from wiki_toolkit.init import INIT_DIRS, INIT_EMPTY_FILES, SCHEMA_TEMPLATE, run_init

if TYPE_CHECKING:
    from pathlib import Path


def test_run_init_creates_all_structure_on_a_bare_directory(tmp_path: Path) -> None:
    """Init on an empty docs/ dir creates all six items and reports them as created."""
    docs_dir = tmp_path / "docs"

    report = run_init(docs_dir)

    assert set(report.created) == {*INIT_DIRS, *INIT_EMPTY_FILES, "schema.md"}
    assert report.already_present == []
    for name in INIT_DIRS:
        assert (docs_dir / name).is_dir()
    for name in INIT_EMPTY_FILES:
        assert (docs_dir / name).is_file()
        assert not (docs_dir / name).read_text(encoding="utf-8")
    assert (docs_dir / "schema.md").is_file()


def test_run_init_writes_schema_matching_toolkit_spec_verbatim(tmp_path: Path) -> None:
    """schema.md's content is a literal string match to the toolkit-spec.md template."""
    docs_dir = tmp_path / "docs"

    run_init(docs_dir)

    assert (docs_dir / "schema.md").read_text(encoding="utf-8") == SCHEMA_TEMPLATE


def test_run_init_is_idempotent_and_never_clobbers_existing_files(tmp_path: Path) -> None:
    """Re-running init against a partially-scaffolded tree leaves existing items untouched."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "schema.md").write_text("hand-written", encoding="utf-8")

    report = run_init(docs_dir)

    assert "schema.md" in report.already_present
    assert "schema.md" not in report.created
    assert (docs_dir / "schema.md").read_text(encoding="utf-8") == "hand-written"

    second_report = run_init(docs_dir)

    assert set(second_report.already_present) == {*INIT_DIRS, *INIT_EMPTY_FILES, "schema.md"}
    assert second_report.created == []
