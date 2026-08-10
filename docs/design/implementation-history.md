# Implementation history

How the pitch's toolkit ([idea.md](idea.md) → [toolkit-spec.md](toolkit-spec.md) → [v1-spec.md](v1-spec.md)) actually got built, across two closed Wayfinder maps and their follow-on tickets. This is the connective narrative; the individual resolved decisions live in [`docs/adr/`](../adr/) — link there for the "why," not here.

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
- **[#54](https://github.com/callowayproject/wiki-toolkit/issues/54) — settings, init, config show** (closed 2026-08-07): filled the gap between what `v1-spec.md` already specified (a `docs_dir` precedence chain, an `init` command) and what existed in code (neither). → [ADR-0007](../adr/0007-settings-resolution-and-init.md)

## Phase 2 — Skills package ([map #62](https://github.com/callowayproject/wiki-toolkit/issues/62), closed 2026-08-08)

Scope: package the five agent-facing `SKILL.md` files (`ingest`, `query`, `lint`, `source-update`, `maintain`) as a standalone, installable Claude Code plugin, and make `init`/`doctor` keep a per-wiki local copy in sync with it. Four design questions:

| Question | Resolved as | ADR |
|---|---|---|
| Packaging format | Claude Code plugin (`.claude-plugin/` + `skills/`) | [0008](../adr/0008-skills-packaged-as-claude-code-plugin.md) |
| Package location | This repo's root, sibling to `wiki_toolkit/` | [0008](../adr/0008-skills-packaged-as-claude-code-plugin.md) |
| Local-copy sync mechanism | Versioned/pinned copy + `doctor` drift warning | [0009](../adr/0009-local-skill-copy-versioned-sync.md) |
| `source-update` without adapters | Git-history-driven, always `needs-review`; comments route to `ingest` | [0010](../adr/0010-source-update-redefined-without-adapters.md) |

[#68](https://github.com/callowayproject/wiki-toolkit/issues/68) turned those four decisions into a build spec; #69–#75 implemented it: the plugin scaffold plus `ingest`/`query` (#70), `lint` (#71), `source-update` (#72), `maintain` (#73), `init`'s skills-copy scaffolding (#74), and `doctor`'s drift check (#75) — shipped as `wiki-toolkit` 0.18.0–0.18.2.

## What's still open

Neither phase touched idea.md's [Gaps section](idea.md) — the receiver's security boundary for untrusted external content, whether PR-review friction suppresses automated updates in practice, or whether the wiki should live in the code repo or a separate one. Those remain unresolved and are not implicitly closed by anything built here; source adapters (GitHub/Jira/Confluence), webhook wiring, the hosted-agent receiver, and real GitHub PR creation are all still future work.

## Where to look

- **Resolved decisions, with context and consequences**: [`docs/adr/`](../adr/)
- **CLI reference, as built**: [v1-spec.md](v1-spec.md)
- **Full eventual toolkit vision** (adapters, webhooks) — superseded by v1-spec.md wherever they disagree: [toolkit-spec.md](toolkit-spec.md)
- **Domain vocabulary**: [CONTEXT.md](CONTEXT.md)
