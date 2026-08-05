"""Unit tests for wiki_toolkit._io's JSONL read/write."""

from typing import TYPE_CHECKING

from wiki_toolkit._io import read_jsonl, write_jsonl

if TYPE_CHECKING:
    from pathlib import Path


def test_read_jsonl_missing_file_returns_empty(tmp_path: Path) -> None:
    """A missing JSONL file reads as an empty list, not an error."""
    assert read_jsonl(tmp_path / "missing.jsonl") == []


def test_read_jsonl_round_trips_write_jsonl(tmp_path: Path) -> None:
    """read_jsonl parses exactly what write_jsonl wrote."""
    path = tmp_path / "f.jsonl"
    records = [{"a": 1}, {"b": 2}]

    write_jsonl(path, records)

    assert read_jsonl(path) == records
