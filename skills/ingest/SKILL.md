---
name: ingest
description: Drive a brand-new or updated source through the wiki_toolkit write gate using the `wiki-toolkit` CLI (`source-scan`, `build`, `lint`, `log`, `propose-pr`). Use when the user says "ingest this source", "add this to the wiki", "process this ticket/PR/doc into the wiki", or points at a file under docs/sources/ that hasn't been written up yet.
---

# ingest

You are ingesting source documents into an Obsidian wiki.
Your job is not to summarize, it is to distill and integrate knowledge across the entire wiki.
Every step in this sequence is required, in order.
Do not skip straight to writing the page.

This sequence covers a session ingesting one or more sources, listed manually.

## Sequence

1. **`wiki-toolkit source-scan --update`**
   Run once at the start of the session, covering every source in `docs/sources/`
   in a single call. Classifies every source file as new, update, or duplicate
   and writes the result to `source-manifest.jsonl`.
   If a source needs `--accept-covered` (an update to a source already covered by a wiki note),
   re-run with that flag once you've confirmed the update is real.

2. **For each source in the session, write or update the wiki page(s)** in
   `wiki/`, following `schema.md`:
   - YAML frontmatter (`title`, `created`, `updated`, `tags`, `sources`,
     `source_count`, `status`) — `source_count` must equal `len(sources)`.
   - Every tag must already exist in `schema.md`'s tag taxonomy; add the tag first if it's new.
   - At least 2 outbound `[[wikilink]]`s to other wiki pages.
     If fewer than 2 related pages exist, create minimal stub pages for the most important concepts mentioned.
   - Cite the source: list its id under `sources:` frontmatter, and add `^[source_id]` at the end of any paragraph whose
     claim comes from a specific source when the page synthesizes 3+ sources.
   - If the source is `proposed` (not yet resolved), mark the page (or the
     relevant section) `status: proposed` / "Proposed change".
   - **Confidence markers** (optional). Mark a claim `^[inferred]` when it's an
     LLM-synthesized connection the source doesn't state directly, or
     `^[ambiguous]` when sources disagree or are unclear; leave a faithful
     paraphrase unmarked (extracted). When a claim also needs a `^[source_id]`
     citation, stack them as independent suffixes with the confidence marker
     first: `^[inferred]^[design-doc-3]`. If you add the page-level
     `confidence:` frontmatter rollup, it must exactly match the inline
     markers: count one unit per bullet line if the page has any bullets,
     else one unit per paragraph; each unit is `inferred`/`ambiguous` per its
     marker, else `extracted`; roll each state up as `count / total`, rounded
     to 2 decimals round-half-up. `lint` checks this rollup for drift, so
     recompute it by hand (or omit `confidence:` entirely) rather than
     guessing — omitting the block is not an error.
   - **Typed relationships** (optional). Add a `relationships:` entry to
     enrich an existing `[[wikilink]]` already in the page body — never as a
     duplicate link with no corresponding wikilink. Each entry is
     `{target: "[[Page]]", type: "..."}` with `type` one of `extends`,
     `implements`, `contradicts`, `derived_from`, `uses`, `replaces`,
     `related_to`, and direction is always from this (the declaring) page's
     perspective. Only pick a specific type when the source material makes
     direction/type clear; otherwise use `related_to` or omit the entry
     rather than fabricating one.
   - Use the [ingest-prompts](ingest-prompts.md) for writing pages.
   - **`wiki-toolkit log --action ingest --title "..." --details "..."`**
     Once per source, right after that source's page(s) are written. Appends
     a structured entry to `docs/log.jsonl` describing what was ingested.

3. **`wiki-toolkit build`**
   Regenerates `docs/catalog.jsonl` from `docs/wiki/`.
   Run once, after every page in the session has been written — not after each individual page.

4. **Invoke the `cross-linker` skill.** Run once, after `build` and before
   `lint`, over every page the session wrote or updated. It scores and
   applies cross-references to the rest of the wiki and infers relationship
   types for the links it adds; see [cross-linker](../cross-linker/SKILL.md)
   for its own sequence.

5. **`wiki-toolkit lint`**
   Run once, after `cross-linker`. Validates frontmatter, tag taxonomy,
   source links, and `source_count`. Fix any `[VIOLATION]` it reports and
   re-run `lint` until it passes clean.

6. **`wiki-toolkit propose-pr --pages <path> --frame routine`**
   Stages the whole session as a single local git branch + commit (repeat
   `--pages` for every page written across every source in the session). This
   never pushes or opens a real PR — it only creates the local commit for a
   human to push and open a PR from. Use `--frame needs-review` instead of
   `routine` when the change is speculative, contested, or otherwise needs
   more than a rubber stamp.

## Rules

- Never write a wiki page without a corresponding source in `docs/source-manifest.jsonl` — run `source-scan` first.
- Never skip `build`, `cross-linker`, or `lint` between writing pages and
  proposing them. `propose-pr` should always land on a lint-clean catalog.
- One session = one `source-scan --update` call, one `build` call, one
  `cross-linker` invocation, one `lint` call, one `log` entry per source
  (plus one per page `cross-linker` links), and one `propose-pr` call —
  regardless of how many sources or pages the session covers. A
  single-source session is just the degenerate case of this same sequence.
- This sequence covers first-time `ingest` only. `source-update` (mutation-triggered
  re-ingest) keeps its own one-PR-per-delta behavior, unaffected by this ticket.

## Batch-dispatched sessions (large source folders)

When a session's sources come from `wiki-toolkit batch-plan <vault> <source-dir>`
instead of a manual list, you (the top-level session) act as **coordinator**: you
dispatch one subagent per batch to read and distill in parallel, but you are the
only one who ever writes to `docs/wiki/` or touches git. This still follows the
same one-session-one-PR sequence above — only step 2 changes.

1. `wiki-toolkit source-scan --update`, same as a manual session.
2. `wiki-toolkit start-branch --frame <routine|needs-review>` — open the
   session's branch once, before dispatching anything. Every commit below,
   and the closing `propose-pr` call, land on this same branch.
3. Run `wiki-toolkit batch-plan <vault> <source-dir>` and dispatch one subagent
   per batch. Each subagent:
   - Reads and distills its assigned files only — it never writes to `docs/wiki/`.
   - Drafts its pages under `docs/_staging/batch-<id>/` (git-ignored — confirm
     `docs/_staging/` is in `.gitignore`; add it if missing) instead of
     returning page content in its response, so the coordinator never pays to
     echo large drafted content back through.
   - Replies with a manifest only: `[{staged_path, dest_path, source_id}, ...]`.
4. As each subagent's manifest arrives — do not wait for the rest of the
   wave — for every entry:
   - Move `staged_path` to `dest_path`.
   - `wiki-toolkit commit-pages --pages <dest_path> --message "Ingest <source_id>: ..."`
   - `wiki-toolkit log --action ingest --title "..." --details "..."` for that source.
5. Once every subagent has reported and been committed, delete `docs/_staging/`
   entirely.
6. Close exactly as a manual session does: one `wiki-toolkit build`, one
   `cross-linker` invocation (once for the whole session, over every page
   from every batch — not once per batch), one `wiki-toolkit lint`, one
   `wiki-toolkit propose-pr --pages <every dest_path from every batch>
   --frame <same frame as step 2>`. `propose-pr` detects that it's already
   on the branch opened in step 2, reuses it instead of opening a second
   one, and is a no-op commit-wise for pages already landed by step 4's
   streaming commits.

Rules specific to batch sessions:
- No git-level merge or conflict handling is needed anywhere in this flow —
  subagents never write or commit, so there is only ever one writer.
- `docs/_staging/` must be empty/removed by the time the session ends,
  regardless of how many batches ran.
- All commits from every batch land on the one branch opened in step 2 — one
  PR for the whole session, same rule as a manual multi-source session.
