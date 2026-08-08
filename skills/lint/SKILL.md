---
name: lint
description: Audit an LLM Wiki with `wiki-toolkit lint`, `source-lint`, and `source-coverage`, then a semantic pass for contradictions, staleness, and orphan pages. Use when the user says "lint the wiki", "check the wiki for issues", "audit the wiki", "find orphan pages", or invokes `maintain`, which runs this as its structural-check step.
---

# lint

Find what's wrong with the wiki. Deterministic checks first, semantic
judgment second. Only the mechanical fixes get written back — everything
else is reported for a human to decide.

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
     sources suggest is now `resolved`, or a claim a newer source has
     superseded.
   - **Orphan pages** — a page with no inbound `[[wikilink]]` from any other
     page.
   - **Missing cross-references** — clearly related pages that don't link to
     each other.

3. **Route fixes by kind:**
   - **Mechanical, safe** (e.g. adding an obviously missing wikilink between
     two related pages): fix it, then run the same write gate as `ingest` —
     `build` -> `lint` -> `log --action lint --title "..." --details "..."`
     -> `propose-pr --frame needs-review`.
   - **Contradictions and staleness**: never resolved unilaterally. List them
     in the report with the pages/sources involved; let a human decide.

## Rules

- Never silently fix a contradiction or staleness finding — those always go
  through the report, not the write gate.
- A mechanical fix that goes through the write gate always uses
  `--frame needs-review`, not `routine` — lint-driven edits weren't the
  point of the user's ask, so they get a closer look.
- Re-run `wiki-toolkit lint` after any write-gate fix and confirm it's clean
  before logging and proposing.
- One lint pass = one report covering all four semantic categories, even if
  some are empty — don't stop after the first finding.
