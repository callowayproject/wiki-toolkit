# ADR-0010: source-update skill redefined without adapters

- **Status:** Accepted
- **Date:** 2026-08-08
- **Source tickets:** [#66](https://github.com/callowayproject/wiki-toolkit/issues/66),
    [#67](https://github.com/callowayproject/wiki-toolkit/issues/67) (implemented in
    [#68](https://github.com/callowayproject/wiki-toolkit/issues/68)–[#73](https://github.com/callowayproject/wiki-toolkit/issues/73))

## Context

toolkit-spec.md's `source-update` skill was written against a live adapter interface
(`fetch`/`diff` against a source system, triggered by a webhook, branching on comment-vs-field-edit mutation type).
v1 has no adapters, but already has `source-delta`/`source-snapshot` CLI commands
that diff a Raw file's current state against its last-known git revision
([ADR-0004](0004-git-history-as-revision-store.md)).
Separately, `toolkit-spec.md` marks `ingest`/`query`/`lint`/`maintain` as "unchanged from `llm-breakdown.md`" —
that claim needed checking against v1's actual command names and identity model
([ADR-0001](0001-source-identity-and-drop-zone-layout.md), [ADR-0003](0003-v1-command-surface-consolidation.md)).

## Decision

- `source-update` triggers via direct invocation on a known source, or via `maintain`'s periodic sweep
    (`source-scan` classifying a file `update`) — never a webhook.
- New comments are out of scope for `source-update` entirely: in v1 they materialize as brand-new Raw source files
    (a new `source` id), classified `new` by `source-scan`, and route through `ingest` instead.
    The original comment-vs-field-edit branch is dropped.
- Because only field edits reach `source-update` by construction, its resulting PR is always framed `needs-review` —
    never `routine` — with `changed_fields` from `source-delta` called out explicitly
    so a reviewer knows what to re-verify.
- The dead `Delta.new_comment_ids` field
    (never populated once the comment branch was dropped) is removed from the `Delta` dataclass.
- None of `ingest`/`query`/`lint`/`maintain` port from `llm-breakdown.md` as-is; each is adapted to v1's actual surface:
    - `ingest`: `source-scan --update` → write/update page(s) → `build` → `lint` → `log --action ingest` →
      `propose-pr --frame routine`.
    - `query`: `search-catalog` replaces the (nonexistent-in-v1) `index.md` read step;
      a filed-back synthesis follows the same write gate as `ingest`.
      Answering alone is never a write.
    - `lint`: deterministic CLI checks first
      (`lint`, `source-lint`, `source-coverage`),
      then an agent semantic pass for contradictions/staleness/orphans/missing cross-refs —
      things the CLI can't check structurally.
      Mechanical fixes route through the write gate; contradictions/staleness are surfaced, not resolved unilaterally.
    - `maintain`: orchestrates `lint` and `source-update`'s sweep trigger rather than duplicating their logic;
      agent-surfaced suggestions are logged individually via `log --action lint`.

## Consequences

- All five `SKILL.md` files are keyed to v1's actual command names
    and the `source`/`processed`/`duplicate` vocabulary in `CONTEXT.md`,
    not the adapter-era language in `toolkit-spec.md`'s Skills section.
