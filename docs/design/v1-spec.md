# wiki_toolkit v1 — Build Spec

Consolidates [toolkit-spec.md](toolkit-spec.md) (target design), `Reference/llm-breakdown.md` Step 04 (base `wiki_tool.py` command set), and [Issue #2](https://github.com/callowayproject/wiki-toolkit/issues/2)'s resolved decisions (#3–#7) into one implementation-ready reference. Where this doc and toolkit-spec.md disagree, **this doc wins for v1** — toolkit-spec.md describes the full eventual toolkit including adapters; this is the narrower slice being built now. See [CONTEXT.md](../../CONTEXT.md) for terminology.

## Scope

v1 is a CLI (`wiki_toolkit`) that consumes **pre-materialized Markdown files** dropped into `docs/sources/` — no adapter fetches or converts anything. `propose-pr` stops at a local branch + commit, not a real GitHub PR.

**Out of scope:** source adapters (GitHub/Jira/Confluence), the five `SKILL.md` agent-facing skill files, webhook wiring, real PR creation, pilot-repo rollout.

## Wiki structure

```text
repo-root/
└── docs/
    ├── catalog.jsonl          # Index of wiki notes
    ├── log.jsonl              # Append-only chronological event log
    ├── schema.md              # Agent-facing instructions for managing this wiki
    ├── source-manifest.jsonl  # Index of sources
    ├── sources/                # Raw source files (drop zone AND processed store — no staging dir)
    └── wiki/                   # Compiled wiki notes
```

## Stack

- **CLI**: `click`
- **Frontmatter parsing**: `python-frontmatter`
- **Kept from scaffold**: `orjson`, `pydantic-settings`
- **Stripped as template cruft**: `fastapi[standard]`, all `opentelemetry-*` packages, `structlog`
- Uncomment `[project.scripts]` (`wiki-toolkit = wiki_toolkit.cli:cli`) once the CLI module exists.

**Architecture constraint**: the CLI is a thin adapter (arg parsing, delegation, output formatting). All business logic lives in internal library functions the CLI calls — the CLI has no logic worth unit-testing beyond correct delegation.

## Source lifecycle

Files land directly in `docs/sources/` — no separate staging/inbox directory. State is tracked entirely via frontmatter:

- **`source`** (required): unique identifier for this source. A URI is recommended. This is the only identity field in v1 — no `source_id`/`stable_id` split (that distinction is adapter-era, out of scope).
- **`processed`** (bool, default `false` / treated as `false` if missing): only the toolkit CLI ever sets this `true`; upstream materializers never do. "Brand-new" vs. "known source needing reprocessing" both read as `processed: false` — telling them apart is `source-scan`'s job, via manifest lookup.
- **`duplicate`** (bool): set by `source-scan` when a `source` id appears under more than one filename. The first-seen file stays canonical and keeps processing normally; later files with the same `source` are stamped `duplicate: true` and excluded from `source-scan`/`build` until a human resolves them via `source-dedupe`.

**Updates** overwrite the same file path (not a new filename); omitting/resetting `processed` on the overwrite signals "needs reprocessing."

**Processed vs. covered** (distinct states, both legitimate independently):
- *Processed* — toolkit has scanned it, not a duplicate/error.
- *Covered* — at least one wiki note's `sources:` frontmatter references it (tracked as `covered_by` in the manifest). Processed-but-not-covered is an expected transient state; `source-lint` flags sources stuck there as a backlog signal, not an ingest-time error.

## Two source kinds

- **Version-controlled** (source code, PRs) — never copied into `sources/`; cited by `{repo, path, commit_sha}`. Out of scope for v1 scanning (`source-scan` skips these — no adapters to produce them yet).
- **Snapshot source** (Jira, Slack, external wiki pages) — anything without its own version history. Copied into `sources/` as Markdown because the toolkit must create the history the source system doesn't provide.

## Deltas and revisions (`source-delta`)

Git history is the storage mechanism for prior states — no separate snapshot store.

- **Current state** = the working-tree file.
- **Last-known revision** = the prior version of that path as of the last commit on `main` (not current HEAD, not whatever branch is checked out) — so `source-delta` always answers "has the canonical (merged) state changed," matching the write gate's "main is truth" model.
- **Diff scope**: only source-content fields (status, description, assignee, etc.) are compared. CLI-owned bookkeeping fields (`processed`, `duplicate`, `source`) are excluded — they're toolkit noise, not source changes.
- **First-time ingestion** (no prior commit for that path on `main`): synthetic empty baseline — every content field reports as new (`(None, current_value)`). `source-delta` always produces a `Delta`, no special-case failure.
- **Mechanism**: `git log -1 --format=%H main -- <path>` to find the last commit touching the path, `git show <sha>:<path>` to read its content, diff only source-content fields.
- **Requires full git history** (`fetch-depth: 0`); `doctor` should detect and warn on a shallow clone, since a shallow clone would make any but the most recent commit indistinguishable from "first-time ingestion."

## Source manifest (`source-manifest.jsonl`)

- `source`: unique identifier
- `path`: relative path from repo root
- `title`: document title or filename
- `referenced_by`: relative paths of wiki documents that reference this file
- `updated`: ISO-8601 date-time
- `update_sha`: SHA of the last-processed commit (or computed SHA of files for mutable sources)
- `status`: `proposed` (ingested ahead of any code change — wiki page is speculative) or `resolved` (a PR has since referenced this source, confirming it against an actual diff)
- `covered_by`: relative paths of wiki notes that cite this source

## Catalog (`catalog.jsonl`)

- `path`, `title`, `updated`
- `sources`: list of `source` ids this document references
- `status`: `resolved` when all referenced sources are `resolved`; `proposed` if any is `proposed`

## Log (`log.jsonl`)

Append-only. Fields: `date` (ISO-8601), `action` (`ingest`, `update`, `lint`, `create`, `archive`, `delete`), `message`, `details`.

## Schema (`schema.md`)

Agent-facing instructions the AI operator follows when writing to the wiki (file naming, frontmatter shape, `[[wikilinks]]` minimum, tag taxonomy, proposed/resolved propagation rules). Content unchanged from toolkit-spec.md's template — v1 just needs the file to exist; the toolkit doesn't generate or validate its prose, only that referenced fields (`catalog.jsonl`/`log.jsonl` entries) stay in sync.

## Write gate

Every wiki write goes through a PR — no direct commits, for either agent-authored content or deterministic tooling output. In v1, `propose-pr` stops at a local branch + commit (no real GitHub PR).

## Command surface

All commands are keyed off `source` (frontmatter field, formerly called `source_id`/`stable_id` in earlier drafts — see [CONTEXT.md](../../CONTEXT.md)). No adapter arguments in v1.

| Command | Contract |
|---|---|
| `doctor` | Non-mutating health check: `docs/` folder structure, Python version, catalog/manifest sanity, note counts, shallow-clone warning |
| `build` | Generate `docs/catalog.jsonl` from `docs/wiki/` notes (no `index.md`/per-folder index generation) |
| `lint` | Validate wiki note frontmatter, allowed tags, source links, `source_count` |
| `source-scan [--update] [--accept-covered]` | Walk `docs/sources/`; classify each file `new` / `update` / `duplicate` (absorbs the old `source-match` and base-spec `source-delta` meaning — "not in the manifest" is just "unprocessed"). With `--update`, write results to `docs/source-manifest.jsonl`. Skips version-controlled source types (no Raw file to scan) |
| `source-lint` | Validate source frontmatter and coverage state (flags `processed` sources with no `covered_by` entries) |
| `source-delta <source>` | Diff a known source's current content against its last-known revision; print `Delta` (`new_comment_ids`, `changed_fields`) |
| `source-coverage` | Show which sources in `docs/sources/` are covered by wiki notes |
| `source-snapshot <source> --units comments\|fields` | Write the new Raw snapshot unit(s) for the given mutation type |
| `source-dedupe` | List `duplicate: true` files with rule-based (mtime/content-similrity) keep/discard suggestions; human confirms/executes — not auto-resolved |
| `search-catalog --query "text"` | Search compiled wiki notes through the catalog |
| `log --title "..." --details "..."` | Append entry to `docs/log.jsonl` |
| `propose-pr --pages <list> --frame routine\|needs-review` | Branch + commit locally, framed per mutation type that triggered it (no real GitHub PR in v1) |

## Testing strategy

Two required layers, following from the thin-CLI architectural constraint:

- **Unit tests** on internal functions: source classification (new/update/duplicate), delta computation, frontmatter diffing, etc. — where real coverage lives.
- **CLI-invocation tests** via `click.testing.CliRunner`: assert each command parses args correctly, calls the right internal function, and produces the right exit code/output. No re-testing of business logic already unit-tested.
- No golden-file byte-diff comparisons against `catalog.jsonl`/`log.jsonl` — structured assertions on parsed output instead.

**`source-delta` fixture uses real git**: a pytest fixture inits a throwaway repo in `tmp_path`, commits an initial source-file version ("last known"), then mutates the file on disk uncommitted ("current"). Exercises real `git log`/`git show`, including the no-prior-commit and shallow-clone edge cases.

**Fixture strategy**: per-command isolated fixtures via a shared factory helper (e.g. `make_source(tmp_path, source, status=..., ...)`) — not one shared "golden wiki" repo.

**Definition of Done**:
- Every command above has (a) unit test coverage for its internal logic, (b) a `CliRunner` adapter test verifying delegation/exit codes/output.
- `mypy`, `ruff`, and pre-commit all pass clean.
- `doctor` run against a real fixture repo state passes.

Fixture/factory file locations (e.g. `tests/conftest.py` layout) are left to the build session — mechanical, doesn't affect any resolved decision above.
