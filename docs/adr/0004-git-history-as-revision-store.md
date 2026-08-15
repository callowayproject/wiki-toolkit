# ADR-0004: Git history as the last-known-revision store

- **Status:** Accepted
- **Date:** 2026-08-04
- **Source tickets:** [#6](https://github.com/callowayproject/wiki-toolkit/issues/6)

## Context

`source-update`'s delta computation needs a "last known" state to diff a source's current field content against.
`docs/sources/` is itself a git-versioned directory inside this repo,
raising the question of whether the toolkit needs its own separate snapshot store or can lean entirely on git.

## Decision

- No separate snapshot database.
    Git history _is_ the storage mechanism for prior state.
- **Current state** = the working-tree file.
- **Last-known revision** = the file's content as of the last commit touching that path on `main` —
    via `git log -1 --format=%H main -- <path>` then `git show <sha>:<path>` — not `HEAD`,
    not whatever branch is checked out, so `source-delta` always answers "has the canonical (merged) state changed."
- Diff scope excludes CLI bookkeeping fields
    (`processed`, `duplicate`, `source`); only source-content fields are compared.
- First-time ingestion (no prior commit on `main` for that path) diffs against a synthetic empty baseline —
    every field reports as new — rather than erroring.
- Requires full git history (`fetch-depth: 0`); `doctor` detects and warns on a shallow clone,
    since a depth-1 checkout makes any prior state indistinguishable from "first-time ingestion."

## Consequences

- `source-delta`'s tests must exercise a real throwaway git repo, not mocked `git` calls —
    see [ADR-0005](0005-two-layer-testing-strategy.md).
- `doctor`'s shallow-clone check exists solely to protect this mechanism from silently misreporting deltas.
