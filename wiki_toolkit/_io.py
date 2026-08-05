"""Shared JSONL read/write helpers, internal to wiki_toolkit."""

from typing import TYPE_CHECKING

import orjson

if TYPE_CHECKING:
    from pathlib import Path


def write_jsonl(path: Path, records: list[dict]) -> None:
    """Write `records` to `path` as JSONL, one object per line."""
    lines = [orjson.dumps(record).decode() for record in records]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def read_jsonl(path: Path) -> list[dict]:
    """Read a JSONL file into a list of dicts. Returns an empty list if the file doesn't exist."""
    if not path.is_file():
        return []
    return [orjson.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
