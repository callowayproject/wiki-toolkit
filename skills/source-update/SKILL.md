---
name: source-update
description: Refresh wiki pages that cite a known source whose content changed, using `wiki-toolkit source-scan --update` and `source-delta`. Use when the user says "update the wiki for this source", "this ticket's fields changed", or invokes `maintain`'s sweep and finds sources classified `update`. New comments on a source are out of scope — those are new Raw sources classified `new`, and route through `ingest` instead.
---

# source-update

Refresh the wiki page(s) that cite a source whose fields changed since the
last-known revision on `main`. This is not for new sources or new comment
threads — those are `new` in `source-scan` and go through `ingest`.

## Sequence

1. **`wiki-toolkit source-scan --update --accept-covered`**
   Classifies every file in `docs/sources/`. Only entries classified
   `update` are this skill's input. `--accept-covered` is required here —
   by definition every source this skill handles is already covered by a
   wiki note, and the scan refuses to write an `update` entry for a covered
   source without it. Entries classified `new` (including new comments on
   an existing source, which materialize as a new source id) are out of
   scope here — hand those to `ingest` instead.

2. **`wiki-toolkit source-delta <source>`**, for each `update`-classified
   source. Reports `changed_fields` against the last-known revision on
   `main` — `[NEW] field: value` or `[CHANGED] field: old -> new`.

3. **Update the wiki page(s)** under `docs/wiki/` that cite this source, to
   reflect the changed fields. Follow `docs/schema.md` as `ingest` does
   (frontmatter, tag taxonomy, `source_count`, wikilinks, `^[source_id]`
   citations).

4. **`wiki-toolkit build`** then **`wiki-toolkit lint`** — same write-gate
   discipline as `ingest`: fix any `[VIOLATION]` and re-run `lint` until
   clean.

5. **`wiki-toolkit log --action update --title "..." --details "..."`**
   Cite the source id and summarize the delta (which fields changed).

6. **`wiki-toolkit propose-pr --pages <list> --frame needs-review`**
   Always `needs-review`, never `routine` — a field edit may invalidate a
   claim the wiki page already made, so it needs closer review than a
   routine addition. Put `changed_fields` in the PR description (via
   `log --details` and the staged commit) so a reviewer knows what to
   re-verify.

## Rules

- New-comment sources are out of scope: they're classified `new`, not
  `update`, and route through `ingest`.
- The resulting PR is always framed `needs-review`.
- Never skip `build` or `lint` between editing a page and logging/proposing
  it.
