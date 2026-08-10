# ADR-0009: Local skill-copy versioned sync with doctor drift warning

- **Status:** Accepted
- **Date:** 2026-08-08
- **Source tickets:** [#65](https://github.com/callowayproject/wiki-toolkit/issues/65) (implemented in [#74](https://github.com/callowayproject/wiki-toolkit/issues/74), [#75](https://github.com/callowayproject/wiki-toolkit/issues/75))

## Context

`init` scaffolds a local copy of the five skills into a consumer wiki's `docs/.agents/skills/`, so the wiki is self-contained without a live runtime dependency on the plugin ([ADR-0008](0008-skills-packaged-as-claude-code-plugin.md)). Left open: how that local copy stays in sync — or doesn't — as the plugin evolves.

## Decision

- Not a symlink, not a silent verbatim copy with no further sync.
- `init` writes the five `SKILL.md` files plus a single provenance marker, `docs/.agents/skills/.provenance`, recording the installed `wiki_toolkit` package version (`importlib.metadata.version`) at scaffold time.
- `doctor` reads that marker, compares it to the currently-installed package version, and reports drift (both versions) when they differ. Non-mutating — consistent with `doctor`'s existing read-only contract; it never rewrites the local copy or overwrites local edits.
- A second `init` run against an already-scaffolded copy reports it as already-present, following the same idempotency pattern used for every other scaffolded item.

## Consequences

- `DoctorReport.ok` treats drift as blocking, matching how every other tracked condition (e.g. `is_shallow_clone`) already gates `ok`.
- Because the plugin and package version together ([ADR-0008](0008-skills-packaged-as-claude-code-plugin.md)), "installed `wiki_toolkit` version" and "current skill content version" are always the same number — the drift check needs no separate skill-version scheme.
