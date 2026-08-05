"""docs/log.jsonl event logging."""

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal

import orjson

if TYPE_CHECKING:
    from pathlib import Path

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


def append_log_entry(docs_dir: Path, entry: LogEntry) -> None:
    """Append `entry` as one JSONL line to `docs_dir/log.jsonl`, never rewriting existing lines."""
    docs_dir.mkdir(parents=True, exist_ok=True)
    with (docs_dir / "log.jsonl").open("a", encoding="utf-8") as f:
        f.write(orjson.dumps(asdict(entry)).decode() + "\n")
