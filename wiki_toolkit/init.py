"""Scaffolds a bare docs/ tree with the structure `doctor` expects."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from wiki_toolkit.sources import SOURCE_MANIFEST_FILENAME

if TYPE_CHECKING:
    from pathlib import Path

INIT_DIRS = ("sources", "wiki")
INIT_EMPTY_FILES = ("catalog.jsonl", "log.jsonl", SOURCE_MANIFEST_FILENAME)

SCHEMA_TEMPLATE = """# Wiki Schema

## Domain
[What this wiki covers, e.g., "Project XYZ"]

## Conventions
- File names: lowercase, hyphens, no spaces (e.g., `transformer-architecture.md`)
- Every wiki page starts with YAML frontmatter (see below)
- Use `[[wikilinks]]` to link between pages (minimum 2 outbound links per page)
- When updating a page, always bump the `updated` date
- Every new page must be added to `catalog.jsonl`
- Every action must be appended to `log.jsonl`
- When updating a page with a source that has a `proposed` status, mark the page's status as `proposed`.
- When all sources on a page are `resolved`, mark the page's status as `resolved`.
- Mark any sections referencing a proposed source with "Proposed change" or "Future implementation" to indicate it is not yet done.
- On pages that synthesize 3+ sources, append `^[source_id]` at the end of paragraphs whose claims come from a specific source. This lets a reader trace each claim back without re-reading the whole raw file. Optional on single-source pages where the `sources:` frontmatter is enough.

## Wiki Document Frontmatter
  ```yaml
  ---
  title: Page Title
  created: YYYY-MM-DD
  updated: YYYY-MM-DD
  tags: [from taxonomy below]
  sources: [source_id]
  source_count: 1  # must equal len(sources); checked by `lint`
  status: resolved  # or `proposed` for speculative pages ingested ahead of any code change
  ---
  ```

## Tag Taxonomy

Rule: every tag on a page must appear in this taxonomy. If a new tag is needed, add it here first, then use it. This prevents tag sprawl.

- <example tag>
- <another tag>

"""


@dataclass
class InitReport:
    """Result of `init`: which docs/ items were created vs already present."""

    created: list[str] = field(default_factory=list)
    already_present: list[str] = field(default_factory=list)


def run_init(docs_dir: Path) -> InitReport:
    """Scaffold `docs_dir`'s structure. Existing items are left untouched and reported as such."""
    report = InitReport()
    docs_dir.mkdir(parents=True, exist_ok=True)

    for name in INIT_DIRS:
        path = docs_dir / name
        if path.is_dir():
            report.already_present.append(name)
        else:
            path.mkdir(parents=True, exist_ok=True)
            report.created.append(name)

    for name in INIT_EMPTY_FILES:
        path = docs_dir / name
        if path.is_file():
            report.already_present.append(name)
        else:
            path.write_text("", encoding="utf-8")
            report.created.append(name)

    schema_path = docs_dir / "schema.md"
    if schema_path.is_file():
        report.already_present.append("schema.md")
    else:
        schema_path.write_text(SCHEMA_TEMPLATE, encoding="utf-8")
        report.created.append("schema.md")

    return report
