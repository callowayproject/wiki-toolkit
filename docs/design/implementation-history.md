# Implementation history

How `wiki_toolkit` ([idea.md](idea.md) → [toolkit-spec.md](toolkit-spec.md)) actually got built, across closed Wayfinder maps and their follow-on tickets. This is the connective narrative; the individual resolved decisions live in [`docs/adr/`](../adr/) — link there for the "why," not here.

## Phase 1 — v1 CLI ([map #2](https://github.com/callowayproject/wiki-toolkit/issues/2), closed 2026-08-05)

Scope: a CLI (`wiki_toolkit`) that consumes pre-materialized Markdown dropped into `docs/sources/` — no source adapters, no real GitHub PR creation, no agent-facing `SKILL.md` files yet. Five design questions had to resolve before any command ticket could start:

| Question | Resolved as | ADR |
|---|---|---|
| Where do dropped-in source files land? | `sources/` is drop zone *and* processed store, no staging dir | [0001](../adr/0001-source-identity-and-drop-zone-layout.md) |
| CLI framework, stdlib vs. dependencies | `click` + `python-frontmatter`, thin-CLI split | [0002](../adr/0002-cli-framework-and-thin-cli-architecture.md) |
| Merged command surface | `source-scan` absorbs `source-match`; `source-delta` keeps one meaning | [0003](../adr/0003-v1-command-surface-consolidation.md) |
| Last-known-snapshot storage | git history, no separate store | [0004](../adr/0004-git-history-as-revision-store.md) |
| Acceptance/testing strategy | two-layer unit + `CliRunner`, no golden files | [0005](../adr/0005-two-layer-testing-strategy.md) |

Twelve build tickets (#9–#22) then implemented `doctor`, `build`, `lint`, `source-scan`, `source-lint`, `source-coverage`, `source-delta`, `source-snapshot`, `source-dedupe`, `search-catalog`, `log`, and `propose-pr` against those five decisions, closing out the map.

**Follow-on work**, not part of the original map but building directly on its output:

- **[#37](https://github.com/callowayproject/wiki-toolkit/issues/37) — domain-module split** (closed 2026-08-05): `core.py` had grown to 810 lines of six tangled domain concepts with the same directory-walk logic reimplemented six times. Split into `sources.py`/`wiki.py`/`write_gate.py`/`log.py`/`doctor.py`/`_io.py` with zero change to `cli.py`'s observable behavior. → [ADR-0006](../adr/0006-domain-module-split.md)
- **[#54](https://github.com/callowayproject/wiki-toolkit/issues/54) — settings, init, config show** (closed 2026-08-07): filled the gap between what the spec already specified (a `docs_dir` precedence chain, an `init` command) and what existed in code (neither). → [ADR-0007](../adr/0007-settings-resolution-and-init.md)

## Phase 2 — Skills package ([map #62](https://github.com/callowayproject/wiki-toolkit/issues/62), closed 2026-08-08)

Scope: package the five agent-facing `SKILL.md` files (`ingest`, `query`, `lint`, `source-update`, `maintain`) as a standalone, installable Claude Code plugin, and make `init`/`doctor` keep a per-wiki local copy in sync with it. Four design questions:

| Question | Resolved as | ADR |
|---|---|---|
| Packaging format | Claude Code plugin (`.claude-plugin/` + `skills/`) | [0008](../adr/0008-skills-packaged-as-claude-code-plugin.md) |
| Package location | This repo's root, sibling to `wiki_toolkit/` | [0008](../adr/0008-skills-packaged-as-claude-code-plugin.md) |
| Local-copy sync mechanism | Versioned/pinned copy + `doctor` drift warning | [0009](../adr/0009-local-skill-copy-versioned-sync.md) |
| `source-update` without adapters | Git-history-driven, always `needs-review`; comments route to `ingest` | [0010](../adr/0010-source-update-redefined-without-adapters.md) |

[#68](https://github.com/callowayproject/wiki-toolkit/issues/68) turned those four decisions into a build spec; #69–#75 implemented it: the plugin scaffold plus `ingest`/`query` (#70), `lint` (#71), `source-update` (#72), `maintain` (#73), `init`'s skills-copy scaffolding (#74), and `doctor`'s drift check (#75) — shipped as `wiki-toolkit` 0.18.0–0.18.2.

## Phase 3 — Cross-linker skill ([map #94](https://github.com/callowayproject/wiki-toolkit/issues/94), closed 2026-08-10)

Scope: weave newly-ingested pages into the rest of the wiki's knowledge graph automatically, instead of relying on whatever `[[wikilink]]`s the agent happens to add while drafting. No ADRs for this map — its design questions were resolved directly into `toolkit-spec.md`'s schema/CLI surface and the `cross-linker` skill file itself, via [#116](https://github.com/callowayproject/wiki-toolkit/issues/116) (the map's implementation-spec handoff ticket):

| Question | Resolved as |
|---|---|
| Candidate detection at scale | Scope to the session's own pages, not a full-vault rescan; a zero-token literal `grep -F` pre-filter over `catalog.jsonl` titles/aliases before any LLM read (research: issue #97) |
| Scoring rubric | 4-signal composite (exact match, partial match, shared sources, tag overlap, co-citation) with EXTRACTED/INFERRED/AMBIGUOUS tiers (issue #96) |
| Relationship-type inference | Seven fixed sentence patterns, first match in table order wins, default `related_to` (issue #98) |
| Alias/co-citation data | New optional `aliases:` frontmatter field plus `aliases`/`links` catalog fields, both additive with no migration (issue #115) |

[#116](https://github.com/callowayproject/wiki-toolkit/issues/116) turned those decisions into a build spec; #117–#120 implemented it: `aliases`/`links` catalog fields (#117), the deterministic `cross-link-candidates` CLI subcommand (#118), narrowing `lint`'s semantic pass to report-only for cross-references (#119), and the `cross-linker` skill wired into `ingest` between `build` and `lint` (#120).

`docs/design/cross-linker-spec.md` and `cross-linker-scale-research.md` were the map's working design docs (spec draft + prior-art research feeding into it) and are deleted now that it's closed — the as-built behavior lives in `skills/cross-linker/SKILL.md`, and the schema/CLI surface in [toolkit-spec.md](toolkit-spec.md). Two ideas from the spec draft were considered and explicitly dropped rather than carried forward: a git-snapshot/`reset --hard` undo mechanism (the existing `--frame needs-review` PR is the undo path) and misc-page affinity/promotion scoring (this toolkit has no `misc/`/`projects/` folder concept).

## What's still open

Neither phase touched idea.md's [Gaps section](idea.md) — the receiver's security boundary for untrusted external content, whether PR-review friction suppresses automated updates in practice, or whether the wiki should live in the code repo or a separate one. Those remain unresolved and are not implicitly closed by anything built here; source adapters (GitHub/Jira/Confluence), webhook wiring, the hosted-agent receiver, and real GitHub PR creation are all still future work.

## Where to look

- **Resolved decisions, with context and consequences**: [`docs/adr/`](../adr/)
- **CLI reference, as built, plus the still-unbuilt full vision (adapters, webhooks) under "Not yet built" headings**: [toolkit-spec.md](toolkit-spec.md)
- **Domain vocabulary**: [CONTEXT.md](CONTEXT.md)
