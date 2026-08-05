"""Unit tests for wiki_toolkit.log."""

from typing import TYPE_CHECKING

import orjson

from wiki_toolkit.log import append_log_entry, build_log_entry

if TYPE_CHECKING:
    from pathlib import Path


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
