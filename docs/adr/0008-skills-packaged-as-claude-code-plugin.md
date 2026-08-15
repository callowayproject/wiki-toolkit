# ADR-0008: Skills packaged as a standalone Claude Code plugin

- **Status:** Accepted
- **Date:** 2026-08-08
- **Source tickets:** [#63](https://github.com/callowayproject/wiki-toolkit/issues/63),
    [#64](https://github.com/callowayproject/wiki-toolkit/issues/64)

## Context

The five agent-facing `SKILL.md` files
(`ingest`, `query`, `lint`, `source-update`, `maintain`)
needed a distributable format so a repo other than `wiki-toolkit` itself could install them,
rather than each consumer vendoring the files by hand.

## Decision

- Packaging format: a Claude Code plugin — `.claude-plugin/plugin.json` plus `skills/<name>/SKILL.md` × 5,
    one plugin bundling all five skills.
- Location: this repo's root, sibling to `wiki_toolkit/` — distinct from `docs/.agents/skills/`,
    the `init`-scaffolded per-wiki local copy (see [ADR-0009](0009-local-skill-copy-versioned-sync.md)).
- A self-referencing `.claude-plugin/marketplace.json`
    (`source: "./"`)
    lives alongside `plugin.json`, so `/plugin marketplace add` + `/plugin install` work directly against this repo
    without a separate marketplace repo.
- `skills.sh` (which just copies raw `SKILL.md` files, no manifest of its own) is treated
    as a secondary distribution channel only — not built or tested as part of this decision.

## Consequences

- The plugin and the `wiki_toolkit` Python package release together as one version number —
    load-bearing for [ADR-0009](0009-local-skill-copy-versioned-sync.md)'s drift check,
    which compares a scaffolded wiki's local skill-copy version against the installed package version.
