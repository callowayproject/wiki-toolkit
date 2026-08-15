# ADR-0003: v1 command surface consolidation

- **Status:** Accepted
- **Date:** 2026-08-04
- **Source tickets:** [#5](https://github.com/callowayproject/wiki-toolkit/issues/5)

## Context

Two overlapping command lists needed merging: `llm-breakdown.md`'s base `wiki_tool.py` set
(`doctor`, `build`, `lint`, `source-scan`, `source-lint`, `source-delta`, `source-coverage`, `search-catalog`, `log`)
and toolkit-spec.md's adapter-era extensions
(`source-match`, `source-delta`, `source-snapshot`, `source-scan`, `propose-pr`).
Two conflicts blocked a single authoritative list: `source-delta` was defined twice with different meanings
(base spec: "show Raw sources missing from the manifest"; toolkit-spec.md:
"diff current state against last-known snapshot"),
and toolkit-spec.md's commands took `<adapter> <payload>`/`<adapter> <stable_id>` arguments that don't apply
once all adapters are deferred (see [ADR-0001](0001-source-identity-and-drop-zone-layout.md)).

## Decision

- `source-scan` absorbs `source-match`'s job
    (classify new/update/duplicate) — "not in the manifest" is just "unprocessed."
- `source-delta`'s only surviving meaning is toolkit-spec.md's:
    diff a known source's current content against its last-known revision
    (see [ADR-0004](0004-git-history-as-revision-store.md)).
- Every command keys off the `source` frontmatter field; no adapter arguments anywhere in v1.
- Final v1 command list: `doctor`, `build`, `lint`, `source-scan [--update] [--accept-covered]`, `source-lint`,
    `source-delta <source>`, `source-coverage`, `source-snapshot <source> --units comments|fields`, `source-dedupe`,
    `search-catalog --query`, `log`, `propose-pr --pages <list> --frame routine|needs-review`.

## Consequences

- This table is what `v1-spec.md`'s "Command surface" section encodes.
    Later additions (`init`, `config show` — [ADR-0007](0007-settings-resolution-and-init.md)) extended it without
    reopening any of these decisions.
