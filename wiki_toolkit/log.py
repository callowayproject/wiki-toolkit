"""docs/log.jsonl event logging."""

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import orjson

from wiki_toolkit.write_gate import stage_best_effort

LogAction = Literal["ingest", "update", "lint", "create", "archive", "delete"]
ALLOWED_LOG_ACTIONS: tuple[LogAction, ...] = ("ingest", "update", "lint", "create", "archive", "delete")


@dataclass
class LogEntry:
    """A single `docs/log.jsonl` entry."""

    date: str
    action: LogAction
    message: str
    details: str


def build_log_entry(action: str, message: str, details: str) -> LogEntry:
    """Build a `log.jsonl` entry. Raises ValueError if `action` isn't in the allowed set."""
    if action not in ALLOWED_LOG_ACTIONS:
        raise ValueError(f"invalid action {action!r}; must be one of {ALLOWED_LOG_ACTIONS}")
    return LogEntry(date=datetime.now(UTC).isoformat(), action=action, message=message, details=details)  # type: ignore[arg-type]


def append_log_entry(docs_dir: Path, entry: LogEntry, *, stage_root: Path | None = None) -> None:
    """Append `entry` as one JSONL line to `docs_dir/log.jsonl`, never rewriting existing lines.

    If `stage_root` is given, best-effort git-stages `log.jsonl` right after appending.
    """
    docs_dir.mkdir(parents=True, exist_ok=True)
    log_path = docs_dir / "log.jsonl"
    with log_path.open("a", encoding="utf-8") as f:
        f.write(orjson.dumps(asdict(entry)).decode() + "\n")
    if stage_root is not None:
        stage_best_effort(stage_root, [str(log_path)])
