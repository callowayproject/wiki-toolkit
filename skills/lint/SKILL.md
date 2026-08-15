---
name: lint
description: Audit an LLM Wiki with `wiki-toolkit lint`, `source-lint`, and `source-coverage`, then a semantic pass for contradictions, staleness, and orphan pages. Use when the user says "lint the wiki", "check the wiki for issues", "audit the wiki", "find orphan pages", or invokes `maintain`, which runs this as its structural-check step.
---

# lint

Find what's wrong with the wiki.
Deterministic checks first, semantic judgment second.
The semantic pass is report-only — nothing it finds gets written back; it's all handed to a human to decide.
(Adding missing cross-references is cross-linker's job, not lint's.)

## Sequence

1. **Deterministic CLI checks** (run all three, in order):
    - `wiki-toolkit lint` — wiki note frontmatter, tag taxonomy, source links,
   `source_count`.
    - `wiki-toolkit source-lint` — `docs/sources/` frontmatter, plus
   processed-but-uncovered sources reported as backlog.
    - `wiki-toolkit source-coverage` — which sources are cited by at least one
   wiki note, and which aren't.

2. **Semantic pass** over `docs/wiki/`, for what the CLI can't check
   structurally:
    - **Contradictions** — two pages (or a page and a newer source) making
   incompatible claims.
    - **Staleness** — a `proposed` source or page section that current
   sources suggest is now `resolved`, or a claim a newer source has superseded.
    - **Orphan pages** — a page with no inbound `[[wikilink]]` from any other
   page.

3. **Report, don't fix.**
   All three semantic categories are report-only — list them with the pages/sources involved and let a human decide.
   `lint` never writes back for a semantic finding, not even an obviously-safe one.

## Rules

- Never silently fix a contradiction, staleness, or orphan-page finding —
  those always go through the report, not the write gate.
- One lint pass = one report covering all three semantic categories, even if
  some are empty — don't stop after the first finding.
