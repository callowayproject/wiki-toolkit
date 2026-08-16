"""Unit tests for wiki_toolkit.batches."""

from typing import TYPE_CHECKING

from wiki_toolkit.batches import plan_batches

if TYPE_CHECKING:
    from pathlib import Path

BATCH_BYTE_CAP = 100_000
BATCH_FILE_CAP = 20


def test_plan_batches_folder_smaller_than_either_cap(tmp_path: "Path") -> None:
    """A folder well under both caps produces a single batch holding every file."""
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "a.md").write_text("a" * 10)
    (source_dir / "b.md").write_text("b" * 20)

    plan = plan_batches(source_dir, BATCH_BYTE_CAP, BATCH_FILE_CAP)

    assert len(plan.batches) == 1
    assert plan.batches[0].files == ["a.md", "b.md"]
    assert plan.batches[0].total_bytes == 30
    assert plan.stats.total_files == 2
    assert plan.stats.total_bytes == 30
    assert plan.stats.batch_count == 1


def test_plan_batches_exactly_at_file_cap(tmp_path: "Path") -> None:
    """Exactly BATCH_FILE_CAP files fit in one batch; the next file starts a new one."""
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    for i in range(BATCH_FILE_CAP + 1):
        (source_dir / f"f{i:02d}.md").write_text("x")

    plan = plan_batches(source_dir, BATCH_BYTE_CAP, BATCH_FILE_CAP)

    assert plan.stats.total_files == BATCH_FILE_CAP + 1
    assert plan.stats.batch_count == 2
    assert len(plan.batches[0].files) == BATCH_FILE_CAP
    assert len(plan.batches[1].files) == 1


def test_plan_batches_exactly_at_byte_cap(tmp_path: "Path") -> None:
    """A file that lands exactly on BATCH_BYTE_CAP stays in the same batch; the next one starts a new batch."""
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "a.md").write_text("a" * (BATCH_BYTE_CAP - 1))
    (source_dir / "b.md").write_text("b")
    (source_dir / "c.md").write_text("c")

    plan = plan_batches(source_dir, BATCH_BYTE_CAP, BATCH_FILE_CAP)

    assert plan.stats.batch_count == 2
    assert plan.batches[0].files == ["a.md", "b.md"]
    assert plan.batches[0].total_bytes == BATCH_BYTE_CAP
    assert plan.batches[1].files == ["c.md"]


def test_plan_batches_empty_source_dir(tmp_path: "Path") -> None:
    """An empty (or missing) source directory reports zero files and zero batches."""
    source_dir = tmp_path / "source"
    source_dir.mkdir()

    plan = plan_batches(source_dir, BATCH_BYTE_CAP, BATCH_FILE_CAP)

    assert plan.batches == []
    assert plan.stats.total_files == 0
    assert plan.stats.total_bytes == 0
    assert plan.stats.batch_count == 0


def test_plan_batches_respects_non_default_file_cap(tmp_path: "Path") -> None:
    """A smaller batch_file_cap splits files into more batches than the default would."""
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    for i in range(3):
        (source_dir / f"f{i}.md").write_text("x")

    plan = plan_batches(source_dir, BATCH_BYTE_CAP, batch_file_cap=1)

    assert plan.stats.batch_count == 3
    assert [b.files for b in plan.batches] == [["f0.md"], ["f1.md"], ["f2.md"]]


def test_plan_batches_respects_non_default_byte_cap(tmp_path: "Path") -> None:
    """A smaller batch_byte_cap splits files into more batches than the default would."""
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "a.md").write_text("a" * 5)
    (source_dir / "b.md").write_text("b" * 5)

    plan = plan_batches(source_dir, batch_byte_cap=5, batch_file_cap=BATCH_FILE_CAP)

    assert plan.stats.batch_count == 2
    assert [b.files for b in plan.batches] == [["a.md"], ["b.md"]]
