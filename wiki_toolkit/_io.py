"""Shared JSONL read/write helpers, internal to wiki_toolkit."""

from typing import TYPE_CHECKING

import orjson

from wiki_toolkit.write_gate import stage_best_effort

if TYPE_CHECKING:
    from pathlib import Path


def write_jsonl(path: Path, records: list[dict], *, stage_root: Path | None = None) -> None:
    """Write `records` to `path` as JSONL, one object per line.

    If `stage_root` is given, best-effort git-stages `path` right after writing it.
    """
    lines = [orjson.dumps(record).decode() for record in records]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    if stage_root is not None:
        stage_best_effort(stage_root, [str(path)])


def read_jsonl(path: Path) -> list[dict]:
    """Read a JSONL file into a list of dicts. Returns an empty list if the file doesn't exist."""
    if not path.is_file():
        return []
    return [orjson.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
