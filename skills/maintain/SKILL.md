---
name: maintain
description: Run the periodic wiki maintenance sweep, orchestrating `lint`, `source-update`, and `ingest` rather than duplicating their logic. Use when the user says "maintain the wiki", "run the maintenance sweep", "do a periodic wiki check", or invokes a scheduled/manual sweep of the wiki.
---

# maintain

Orchestrate a periodic sweep of the wiki. This skill contains no ingestion or
linting logic of its own — it delegates every actual write to `lint`,
`source-update`, or `ingest`, and only handles the routing between them.

## Sequence

1. **Invoke the `lint` skill in full.** Let it run its own deterministic and
   semantic passes, write its own mechanical fixes through the write gate,
   and produce its own report of contradictions/staleness/orphans for a
   human to decide.

2. **`wiki-toolkit source-scan --update`**
   Classify every file in `docs/sources/`. For each classified entry:
   - `update` -> hand the source to the `source-update` skill.
   - `new` -> hand the source to the `ingest` skill.
   - `duplicate` -> leave for `ingest`'s existing duplicate handling; not
     this skill's concern.

3. **Surface additional suggestions** noticed along the way that aren't
   already covered by steps 1-2:
   - A source worth ingesting that isn't yet under `docs/sources/`.
   - An open question worth investigating.

   Log each one individually — not batched — via
   `wiki-toolkit log --action lint --title "..." --details "..."`, so it
   leaves an auditable trail even if nobody acts on it.

## Rules

- Delegate, don't duplicate: never restate `lint`'s deterministic/semantic
  checks, `source-update`'s delta/rewrite steps, or `ingest`'s write-gate
  sequence here. Invoke those skills and let them run their own sequence.
- Every `update`-classified source goes to `source-update`; every
  `new`-classified source goes to `ingest`. Don't hand-write a wiki page
  directly from this skill.
- Suggestions from step 3 are logged, never acted on unilaterally — they're
  a record for a human, not an instruction to ingest or fix on the spot.
- One sweep = one `lint` invocation, one `source-scan`, and one
  `source-update`/`ingest` dispatch per classified source.
