---
name: ingest
description: Drive a brand-new or updated source through the wiki_toolkit write gate using the `wiki-toolkit` CLI (`source-scan`, `build`, `lint`, `log`, `propose-pr`). Use when the user says "ingest this source", "add this to the wiki", "process this ticket/PR/doc into the wiki", or points at a file under docs/sources/ that hasn't been written up yet.
---

# ingest

Turn one source under `docs/sources/` into a reviewed wiki page. Every step
in this sequence is required, in order — do not skip straight to writing the
page.

## Sequence

1. **`wiki-toolkit source-scan --update`**
   Classifies every file in `docs/sources/` as new, update, or duplicate and
   writes the result to `docs/source-manifest.jsonl`. If a source needs
   `--accept-covered` (an update to a source already covered by a wiki note),
   re-run with that flag once you've confirmed the update is real.

2. **Write or update the wiki page(s)** in `docs/wiki/`, following
   `docs/schema.md`:
   - YAML frontmatter (`title`, `created`, `updated`, `tags`, `sources`,
     `source_count`, `status`) — `source_count` must equal `len(sources)`.
   - Every tag must already exist in `docs/schema.md`'s tag taxonomy; add the
     tag there first if it's new.
   - At least 2 outbound `[[wikilink]]`s to other wiki pages.
   - Cite the source: list its id under `sources:` frontmatter, and add
     `^[source_id]` at the end of any paragraph whose claim comes from a
     specific source when the page synthesizes 3+ sources.
   - If the source is `proposed` (not yet resolved), mark the page (or the
     relevant section) `status: proposed` / "Proposed change".

3. **`wiki-toolkit build`**
   Regenerates `docs/catalog.jsonl` from `docs/wiki/`. Run after every page
   write so the catalog stays in sync.

4. **`wiki-toolkit lint`**
   Validates frontmatter, tag taxonomy, source links, and `source_count`. Fix
   any `[VIOLATION]` it reports and re-run `lint` until it passes clean.

5. **`wiki-toolkit log --action ingest --title "..." --details "..."`**
   Appends a structured entry to `docs/log.jsonl` describing what was
   ingested.

6. **`wiki-toolkit propose-pr --pages <path> --frame routine`**
   Stages the change as a local git branch + commit (repeat `--pages` for
   multiple pages). This never pushes or opens a real PR — it only creates
   the local commit for a human to push and open a PR from. Use
   `--frame needs-review` instead of `routine` when the change is
   speculative, contested, or otherwise needs more than a rubber stamp.

## Rules

- Never write a wiki page without a corresponding source in
  `docs/source-manifest.jsonl` — run `source-scan` first.
- Never skip `build` or `lint` between writing a page and logging/proposing
  it — `propose-pr` should always land on a lint-clean catalog.
- One ingest = one `log` entry and one `propose-pr` call, even when it
  touches several pages.
