# ADR-0011: Batch planning split into its own module

- **Status:** Accepted
- **Date:** 2026-08-13

## Context

[ADR-0006](0006-domain-module-split.md) rejected splitting `sources.py` further by individual command, because every command in it (`scan_sources`, `apply_source_scan`, `lint_sources`, `source_coverage`, `compute_source_delta`, `suggest_dedupe`, `write_source_snapshot`) shares the source manifest and the canonical-source predicate — splitting by command would recreate that duplication one level up.

`plan_batches` (added later, issue #84, after ADR-0006) doesn't share that dependency. It never reads the manifest, never parses frontmatter, never calls `_iter_markdown` or `_is_canonical_source` — it walks raw files under a `source_dir` by byte/count caps, before any file has become a `source` in the domain sense. "Batch" wasn't in `CONTEXT.md`'s glossary despite being used in the CLI (`batch-plan`) and write-gate workflow ("batch coordinator session").

## Decision

- `Batch`/`BatchStats`/`BatchPlan`/`plan_batches` move to a new `batches.py`, with their tests to `test_batches.py`.
- `CONTEXT.md` gains a `Batch` glossary entry, distinguishing it from `source` and `Snapshot source`.
- `sources.py` is otherwise unchanged — ADR-0006's reasoning still holds for the manifest-sharing commands it covers.

## Consequences

- This narrows, not reverses, ADR-0006: the split criterion is "does this command participate in the shared manifest/canonical-source state," not "is this a different command."
- Any future addition to `sources.py` should be checked against that same criterion before being added there by default.
