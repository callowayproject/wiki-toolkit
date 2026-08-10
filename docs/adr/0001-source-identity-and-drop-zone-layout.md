# ADR-0001: Source identity and drop-zone layout

- **Status:** Accepted
- **Date:** 2026-08-04
- **Source tickets:** [#3](https://github.com/callowayproject/wiki-toolkit/issues/3), [#8](https://github.com/callowayproject/wiki-toolkit/issues/8)

## Context

v1 consumes pre-materialized Markdown source files (already converted from GitHub/Jira/Confluence-shaped payloads by something upstream — v1 has no adapters). toolkit-spec.md describes `sources/` as holding versioned snapshots *after* ingestion, which left open whether a separate inbox/staging directory exists for files that haven't been processed yet, and how the toolkit tells "brand-new source" from "not yet processed" from "already processed" without one.

## Decision

- No separate staging/inbox directory. `docs/sources/` is both the drop zone and the processed store, distinguished only by frontmatter.
- `source` is the sole identity field (a URI is recommended). No adapter-level `source_id`/`stable_id` split in v1 — that distinction belongs to a future adapter layer.
- `processed` (bool): defaults to / is treated as `false` when missing. Only the toolkit CLI ever sets it `true`; upstream materializers never do.
- Updates overwrite the same file path (never a new filename); resetting/omitting `processed` on the overwrite is the reprocessing signal.
- `duplicate` (bool): set by `source-scan` when a `source` id appears under more than one filename. The first-seen file is canonical and keeps processing normally; later files with the same id are stamped `duplicate: true` and excluded from `source-scan`/`build` until a human resolves them via `source-dedupe`.

## Consequences

- `source-scan` absorbs what would otherwise have been a separate `source-match` step — "not in the manifest" is simply "unprocessed" (see [ADR-0003](0003-v1-command-surface-consolidation.md)).
- "Processed" and "covered" (referenced by a wiki note's `sources:` frontmatter) are tracked as distinct, independently-true states — processed-but-not-covered is an expected transient backlog state, not an error.
