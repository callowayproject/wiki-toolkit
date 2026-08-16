"""Ingest-dispatch batching for wiki_toolkit.

Splits raw files under a source directory into size/count-bounded batches for parallel
`wiki-ingest` dispatch. Runs before anything becomes a `source` in the domain sense
(no frontmatter, no manifest) -- see ADR-0011.
"""

from dataclasses import dataclass, field
from pathlib import Path

BATCH_BYTE_CAP = 100_000
BATCH_FILE_CAP = 20


@dataclass
class Batch:
    """A single batch of files for parallel ingest dispatch."""

    id: str
    files: list[str] = field(default_factory=list)
    total_bytes: int = 0


@dataclass
class BatchStats:
    """Aggregate totals across a `batch-plan` run."""

    total_files: int
    total_bytes: int
    batch_count: int


@dataclass
class BatchPlan:
    """The full result of a `batch-plan` pass."""

    batches: list[Batch]
    stats: BatchStats


def plan_batches(source_dir: Path) -> BatchPlan:
    """Split the files under `source_dir` into batches of at most `BATCH_BYTE_CAP` bytes or `BATCH_FILE_CAP` files.

    Files are visited in sorted order for determinism. A batch closes as soon as adding the next
    file would cross either cap; a single file larger than `BATCH_BYTE_CAP` still gets its own
    batch rather than being split. Reports zero files if `source_dir` doesn't exist.
    """
    files = sorted(p for p in source_dir.rglob("*") if p.is_file()) if source_dir.is_dir() else []

    batches: list[Batch] = []
    current: Batch | None = None
    for path in files:
        size = path.stat().st_size
        if current is None or len(current.files) >= BATCH_FILE_CAP or current.total_bytes + size > BATCH_BYTE_CAP:
            current = Batch(id=str(len(batches)))
            batches.append(current)
        current.files.append(str(path.relative_to(source_dir)))
        current.total_bytes += size

    stats = BatchStats(
        total_files=len(files),
        total_bytes=sum(b.total_bytes for b in batches),
        batch_count=len(batches),
    )
    return BatchPlan(batches=batches, stats=stats)
