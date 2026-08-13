# LLM Wiki Toolkit — Spec

Specifies `wiki_toolkit`, the AI skills and helper tools that implement [llm-wiki.md](Reference/llm-wiki.md)
as a general-purpose toolkit. An AI Agent harness operates this toolkit; the toolkit itself is
domain-agnostic.

This doc merges what shipped (v1 CLI + skills plugin, see [implementation-history.md](implementation-history.md))
with the still-unbuilt full vision. Content is as-built by default; anything not yet built is called
out explicitly under **"Not yet built"** headings. See [CONTEXT.md](CONTEXT.md) for terminology.

## Wiki structure

The basic layout of the wiki:

```text
repo-root/
└── docs/
    ├── .agents/
    │   └── skills/             # Local copy of the AI Agent skills, scaffolded by `init`
    ├── catalog.jsonl           # Catalog of everything in the wiki
    ├── log.jsonl               # Chronological listing of wiki events
    ├── schema.md               # Evolving description of the wiki
    ├── source-manifest.jsonl   # Index of sources, where they are linked
    ├── sources/                # Raw sources — drop zone AND processed store, no staging dir
    └── wiki/                   # Compiled wiki notes
```

## Stack

- **CLI**: `click`
- **Other dependencies**: `orjson`, `pydantic-settings`, `pyyaml`

**Architecture constraint**: the CLI is a thin adapter (arg parsing, delegation, output formatting).
All business logic lives in internal library functions the CLI calls — the CLI has no logic worth
unit-testing beyond correct delegation.

## Configuration

Settings (currently just the `docs` root, default `docs/`) resolve via `pydantic-settings`, in
precedence order:

1. CLI flag (`--docs-dir`, per-command where relevant)
2. Environment variable (`WIKI_TOOLKIT_DOCS_DIR`)
3. `[tool.wiki_toolkit]` table in the project's `pyproject.toml`, if present
4. Built-in default

No dedicated config file format — reusing `pyproject.toml` avoids introducing a new file the user
has to know about.

## Sources

There are two kinds of sources:

**Version-controlled** (source code, PRs) — never copied into `sources/`; git already has an
immutable history, so duplicating it would be pure redundancy. Cited by `{repo, path, commit_sha}`.
An entry for each file is maintained in `catalog.jsonl`. Out of scope for scanning today —
`source-scan` skips these, since there are no adapters yet to produce them (see "Not yet built"
under Adapter interface, below).

**Snapshot source** (Jira, Slack, Confluence, external wiki pages) — anything without its own
version history. Markdown versioned snapshots of the content are copied into `sources/`, because
the toolkit has to create the history the source system doesn't provide.

A source type must expose a stable external ID (e.g., a URI, Jira ticket key, Slack permalink, or
Confluence page ID) to be eligible for snapshot handling. If a source type can't supply one, the
toolkit refuses automatic ingestion and flags it for manual filing. Fuzzy content-matching is
deliberately excluded as a dedup mechanism, since a false-positive merge in an unattended,
write-capable agent is worse than a missed source.

Within a snapshot source, two mutation types are handled differently:

- **Comments**: each comment on a source is treated as its own source, with its own stable ID.
  No diffing: the toolkit tracks the highest processed comment ID per parent source and treats
  anything newer as new.
- **Field edits**: changes to a source's fields (status, description, assignee, etc.) mutate in
  place. The toolkit diffs the full field state against the last snapshot to produce a delta of
  changed fields.

### Source lifecycle (frontmatter)

Files land directly in `docs/sources/` — no separate staging/inbox directory. State is tracked
entirely via frontmatter:

- **`source`** (required): unique identifier for this source. A URI is recommended. This is the
  only identity field today — no `source_id`/`stable_id` split (that distinction is adapter-era,
  not yet built).
- **`processed`** (bool, default `false` / treated as `false` if missing): only the toolkit CLI
  ever sets this `true`; upstream materializers never do. "Brand-new" vs. "known source needing
  reprocessing" both read as `processed: false` — telling them apart is `source-scan`'s job, via
  manifest lookup.
- **`duplicate`** (bool): set by `source-scan` when a `source` id appears under more than one
  filename. The first-seen file stays canonical and keeps processing normally; later files with the
  same `source` are stamped `duplicate: true` and excluded from `source-scan`/`build` until a human
  resolves them via `source-dedupe`.

**Updates** overwrite the same file path (not a new filename); omitting/resetting `processed` on
the overwrite signals "needs reprocessing."

**Processed vs. covered** (distinct states, both legitimate independently):
- *Processed* — toolkit has scanned it, not a duplicate/error.
- *Covered* — at least one wiki note's `sources:` frontmatter references it (tracked as
  `covered_by` in the manifest). Processed-but-not-covered is an expected transient state;
  `source-lint` flags sources stuck there as a backlog signal, not an ingest-time error.
  `source-lint` and `source-coverage` read `covered_by` straight from the manifest — coverage
  is only as fresh as the last `build`, the same staleness tolerance `build_catalog` already
  applies to a note's `resolved`/`proposed` status.

### Deltas and revisions (`source-delta`)

Git history is the storage mechanism for prior states — no separate snapshot store.

- **Current state** = the working-tree file.
- **Last-known revision** = the prior version of that path as of the last commit on `main` (not
  current HEAD, not whatever branch is checked out) — so `source-delta` always answers "has the
  canonical (merged) state changed," matching the write gate's "main is truth" model.
- **Diff scope**: only source-content fields (status, description, assignee, etc.) are compared.
  CLI-owned bookkeeping fields (`processed`, `duplicate`, `source`) are excluded — they're toolkit
  noise, not source changes.
- **First-time ingestion** (no prior commit for that path on `main`): synthetic empty baseline —
  every content field reports as new (`(None, current_value)`). `source-delta` always produces a
  `Delta`, no special-case failure.
- **Mechanism**: `git log -1 --format=%H main -- <path>` to find the last commit touching the path,
  `git show <sha>:<path>` to read its content, diff only source-content fields.
- **Requires full git history** (`fetch-depth: 0`); `doctor` detects and warns on a shallow clone,
  since a shallow clone would make any but the most recent commit indistinguishable from
  "first-time ingestion."

## Source manifest

The source manifest (`source-manifest.jsonl`) is an index of all sources referenced in the wiki.
The toolkit uses it to determine the potential scope of a change.

### Source manifest schema

- `source`: unique identifier for this document
- `path`: relative path to the document from the repo root
- `title`: document title, or the file name if necessary
- `updated`: ISO-8601 date-time string when it was updated
- `update_sha`: SHA of the Git commit last processed for this file, or the computed SHA of files
  for mutable sources like Jira tickets
- `status`: `proposed` or `resolved`. `proposed` means the source was ingested ahead of any code
  change (a design doc, a ticket) and its wiki page is speculative; `resolved` means a PR has since
  referenced this source, confirming it against an actual diff.
- `covered_by`: relative paths of wiki notes that cite this source. Recomputed by `build` from
  `docs/wiki/` notes' `sources:` frontmatter (see Command surface below) — not hand-edited.

## Catalog

The catalog (`catalog.jsonl`) is an index of all the documents in the wiki (`wiki/`), with
cross-references to the sources they reference.

### Catalog schema

- `path`: relative path to the document from the repo root
- `title`: the document's title
- `aliases`: list of alternate names for the document, from its frontmatter `aliases:` (empty list if absent)
- `links`: list of the document's outbound `[[wikilink]]` targets, extracted from its body (empty list if none); feeds `cross-linker`'s co-citation scoring signal
- `sources`: list of `source` ids this document references
- `updated`: ISO-8601 date-time string when it was updated
- `status`: `resolved` when all referenced sources are `resolved`; `proposed` if any is `proposed`

## Log

The log (`log.jsonl`) is an append-only chronological list of wiki events.

### Log schema

- `date`: ISO-8601 date-time string when the entry was created
- `action`: one of `ingest`, `update`, `lint`, `create`, `archive`, `delete`
- `message`: a one-line summary of the action
- `details`: details about the action

## Schema

The schema (`schema.md`) provides instructions to the AI agent on how to manage this wiki. The AI
agent can modify it. `init` scaffolds it from this built-in template; the toolkit doesn't generate
or validate its prose beyond keeping referenced fields (`catalog.jsonl`/`log.jsonl` entries) in
sync.

````markdown
# Wiki Schema

## Domain
[What this wiki covers, e.g., "Project XYZ"]

## Conventions
- File names: lowercase, hyphens, no spaces (e.g., `transformer-architecture.md`)
- Every wiki page starts with YAML frontmatter (see below)
- Use `[[wikilinks]]` to link between pages (minimum 2 outbound links per page)
- When updating a page, always bump the `updated` date
- Every new page must be added to `catalog.jsonl`
- Every action must be appended to `log.jsonl`
- When updating a page with a source that has a `proposed` status, mark the page's status as `proposed`.
- When all sources on a page are `resolved`, mark the page's status as `resolved`.
- Mark any sections referencing a proposed source with "Proposed change" or "Future implementation" to indicate it is not yet done.
- On pages that synthesize 3+ sources, append `^[source_id]` at the end of paragraphs whose claims come from a specific source. This lets a reader trace each claim back without re-reading the whole raw file. Optional on single-source pages where the `sources:` frontmatter is enough.
- Mark claims with a confidence marker where relevant: no marker = extracted (a paraphrase of what a source actually says); `^[inferred]` suffix = an LLM-synthesized connection or implication the source doesn't state directly; `^[ambiguous]` suffix = sources disagree or are unclear. Default (no marker) means existing pages stay valid without changes. A claim needing both a confidence marker and a `^[source_id]` citation stacks them as independent suffixes, confidence marker first: `^[inferred]^[design-doc-3]`.
- The optional `confidence:` frontmatter block rolls up the mix of markers on the page, one countable unit per bullet (or per paragraph on non-bulleted pages), rounded to 2 decimal places, round-half-up. `ingest` writes it best-effort; `lint` recomputes it from the page's actual markers and flags any drift — exact match after rounding, same as `source_count`, no tolerance band.
- The optional `relationships:` frontmatter block adds typed, directional edges between pages, on top of plain `[[wikilinks]]` (which carry no semantic weight). Rules: omit the block entirely if no typed relationship is known — untagged wikilinks remain valid; if `[[foo]]` already appears as an inline wikilink, a `relationships:` entry just enriches it with a type, it is not a second link; the page declaring the entry is the *source*, `target` is the destination — only declare relationships from this page's own perspective; only add a typed entry when the source material makes the relationship's direction and type clear — when in doubt, use `related_to` or omit. `type` must be one of the fixed Relationship Types below; `target` must resolve to an existing page or `lint` flags it.
- The optional `aliases:` frontmatter field lists alternate names a page is also known by (e.g. an acronym alongside a spelled-out title). It exists to widen `cross-linker`'s literal-match pre-filter beyond the page's canonical `title:` — nothing else reads it. Omit when a page has no alternate names.

## Wiki Document Frontmatter
  ```yaml
  ---
  title: Page Title
  created: YYYY-MM-DD
  updated: YYYY-MM-DD
  tags: [from taxonomy below]
  sources: [source_id]
  source_count: 1  # must equal len(sources); checked by `lint`
  status: resolved  # or `proposed` for speculative pages ingested ahead of any code change
  confidence:  # optional; best-effort fractions written by `ingest`, recomputed and drift-checked by `lint` (see Conventions)
    extracted: 0.72
    inferred: 0.25
    ambiguous: 0.03
  relationships:  # optional; typed, directional edges to other pages
    - target: "[[Transformer Architecture]]"
      type: extends
    - target: "[[LSTM]]"
      type: contradicts
  aliases: [alt name, another alt name]  # optional; alternate names this page is also known by
  ---
  ```

## Tag Taxonomy

Rule: every tag on a page must appear in this taxonomy. If a new tag is needed, add it here first, then use it. This prevents tag sprawl.

- <example tag>
- <another tag>

## Relationship Types

Fixed set — unlike Tag Taxonomy, this list is not per-wiki editable; the same 7 types apply everywhere so edges stay comparable across wikis.

| Type           | Meaning                                                     | Example                                       |
|----------------|--------------------------------------------------------------|------------------------------------------------|
| `extends`      | This page builds on or generalises the target               | GPT extends Transformer Architecture          |
| `implements`   | This page is a concrete realisation of the target concept   | BERT implements Masked Language Modelling     |
| `contradicts`  | This page's claims conflict with or refute the target       | Evidence A contradicts Evidence B             |
| `derived_from` | This page is based on or adapted from the target            | Fine-tuning is derived from Transfer Learning |
| `uses`         | This page depends on or relies on the target                | RAG uses Vector Databases                     |
| `replaces`     | This page supersedes or deprecates the target                | GPT-4 replaces GPT-3                          |
| `related_to`   | Catch-all: related but no stronger directional type applies | Concept A is related to Concept B             |

````

## Write gate

Every wiki write goes through a PR — no exceptions, no direct commits, for either LLM-authored
content or deterministic tooling output (catalog, manifest, log). One rule, no second write path
to audit. Today, `propose-pr` stops at a local branch + commit — no real GitHub PR yet (see "Not
yet built" under Command surface).

## Command surface

All commands are keyed off `source` (frontmatter field, formerly called `source_id`/`stable_id` in
earlier drafts — see [CONTEXT.md](CONTEXT.md)). No adapter arguments yet.

| Command | Contract |
|---|---|
| `init` | Scaffold a new wiki: create `docs/{sources,wiki}/`, empty `catalog.jsonl`/`log.jsonl`/`source-manifest.jsonl`, `schema.md` from the built-in template, and a local `docs/.agents/skills/` copy of the skills plugin |
| `doctor` | Non-mutating health check: `docs/` folder structure, Python version, catalog/manifest sanity, note counts, shallow-clone warning, resolved configuration and its source, local skills-copy version drift |
| `build` | Generate `docs/catalog.jsonl` from `docs/wiki/` notes, including each page's `aliases:` frontmatter and outbound `[[wikilink]]` targets as `links` (both empty lists if absent/none) (no `index.md`/per-folder index generation). Also recomputes `covered_by` in `docs/source-manifest.jsonl` by inverting each note's `sources:` frontmatter into per-source citing-page lists, full overwrite each run (no incremental state). A `sources:` id absent from the manifest is skipped here — `lint` already flags it as an unresolved source reference |
| `lint` | Validate wiki note frontmatter, allowed tags, source links, `source_count`; flags a `relationships:` entry whose `target` doesn't resolve to an existing page, and drift between a page's `confidence:` block and its recomputed marker counts. Flagged, not rejected — the write gate's PR review is the enforcement point |
| `source-scan [--update] [--accept-covered] [--source <id>]` | Walk `docs/sources/`; classify each file `new` / `update` / `duplicate` (absorbs the old `source-match` and base-spec `source-delta` meaning — "not in the manifest" is just "unprocessed"). Classification is always full (cheap, read-only, needed for accurate `needs_attention`/backlog reporting). With `--update`, write/stamp results into `docs/source-manifest.jsonl` and stage the touched files (see Write gate); `--source <id>` narrows that write/stage step to a single classified source, leaving every other classified source unwritten until a later unscoped call (e.g. `maintain`'s sweep) catches it up. Skips version-controlled source types (no Raw file to scan) |
| `source-lint` | Validate source frontmatter and coverage state (flags `processed` sources with no `covered_by` entries) |
| `source-delta <source>` | Diff a known source's current content against its last-known revision; print `Delta` (`new_comment_ids`, `changed_fields`) |
| `source-coverage` | Show which sources in `docs/sources/` are covered by wiki notes |
| `source-snapshot <source> --units comments\|fields` | Write the new Raw snapshot unit(s) for the given mutation type |
| `source-dedupe` | List `duplicate: true` files with rule-based (mtime/content-similarity) keep/discard suggestions; human confirms/executes — not auto-resolved |
| `search-catalog --query "text"` | Search compiled wiki notes through the catalog |
| `cross-link-candidates <page-paths...>` | Literal, case-insensitive title/alias match of `page-paths`' bodies against every other `catalog.jsonl` entry (skipping code blocks, frontmatter, and mentions already wrapped in `[[...]]`); emits one JSONL candidate per line (`page`, `target`, `mention_text`, `match_type`). Zero LLM judgment — scoring and relationship-type inference are `cross-linker`'s job |
| `log --title "..." --details "..."` | Append entry to `docs/log.jsonl` |
| `batch-plan <vault> <source-dir>` | Split the files under `source-dir` into batches (100,000 bytes or 20 files per batch, whichever comes first) for parallel wiki-ingest subagent dispatch; prints `{batches: [{id, files, total_bytes}], stats: {total_files, total_bytes, batch_count}}` |
| `start-branch --frame routine\|needs-review` | Open a session's local branch up front, before any pages are committed — used by a batch coordinator so streaming `commit-pages` calls and the closing `propose-pr` call land on the same branch |
| `commit-pages --pages <list> --message <str>` | Commit exactly what's currently staged onto the currently checked-out branch — `pages` is informational (goes into the commit message), not a git pathspec filter. Every command that mutates a `docs_dir` file (`build`, `cross-linker`, `log`, `source-scan --update`) stages its own output as it writes, so by the time `commit-pages` runs, the git index already holds `pages` plus whatever else that source's producer commands touched. A batch coordinator calls this once per source, as soon as that source's subagent reports back, rather than waiting for the whole batch to finish |
| `propose-pr --pages <list> --frame routine\|needs-review` | Branch + commit locally, framed per mutation type that triggered it (no real GitHub PR yet). Same self-staging contract as `commit-pages`: commits exactly what's staged, `pages` informational only. Because producer commands self-stage at write time rather than `propose-pr` scanning `docs_dir` for dirty files afterward, only what the session's own commands actually touched ever lands in the commit. If the current branch was already opened by `start-branch`, reuses it instead of creating a new one, and tolerates pages already committed via `commit-pages` |
| `config show` | Read-only: print the resolved configuration and which source (default/env/`pyproject.toml`/flag) each value came from |

## Not yet built: adapters

Each source type (GitHub, Jira, ...) would implement:

```
kind(payload) -> "version_controlled" | "snapshot"

stable_id(payload) -> str | None
  # None means: reject, flag for manual filing. Never guess.

locator(payload) -> {repo, path, commit_sha}
  # version_controlled only

fetch(stable_id) -> Snapshot
  # snapshot only
  # Snapshot = {
  #   stable_id: str,
  #   fields: {name: value, ...},
  #   comments: [{comment_id, author, body, created}, ...],
  # }

diff(old_snapshot, new_snapshot) -> Delta
  # Delta = {
  #   new_comment_ids: [comment_id, ...],
  #   changed_fields: {name: (old_value, new_value), ...},
  # }
```

### Planned v1 adapters

- **GitHub** — issues, PRs, Renovate PRs. Already the trigger mechanism per `idea.md`. Dependabot
  PRs are out of scope for the pilot (see `idea.md` Solution section).
- **Jira** — the concrete comment-chain case that motivated this spec.
- **Confluence** — design docs. `stable_id` is the Confluence page ID. Ingesting a design doc ahead
  of any PR produces a `status: proposed` wiki page (see "Write gate" and the source-manifest
  schema above); a later PR that references the same page ID resolves it via the normal
  source-linkage flow, flipping `status` to `resolved`.

Everything else named in `idea.md`'s "Possible sources" list (Slack, Teams, Azure DevOps, Linear)
implements this interface later. No stub code is required now — the interface above is the
contract a future adapter must satisfy.

#### GitHub adapter payload shape

Files named by event; `pull_request` events materialize as:

```markdown
# {title}

{body}
```

References: [`pull_request`](https://docs.github.com/en/webhooks/webhook-events-and-payloads#pull_request), [`pull_request_review`](https://docs.github.com/en/webhooks/webhook-events-and-payloads#pull_request_review), [`pull_request_review_comment`](https://docs.github.com/en/webhooks/webhook-events-and-payloads#pull_request_review_comment), [`pull_request_review_thread`](https://docs.github.com/en/webhooks/webhook-events-and-payloads#pull_request_review_thread).

#### Jira adapter payload shape

An issue and its properties belong to a single snapshot; each comment is its own snapshot ([webhook reference](https://developer.atlassian.com/cloud/jira/platform/webhooks/)).

**Issues** — file named `{issue-key}.md`. Webhooks: `jira:issue_created`, `jira:issue_updated`, `jira:issue_deleted`; issue-property webhooks `issue_property_set`, `issue_property_deleted`.

```markdown
# Main order flow broken

id: 10002
key: ED-1
url: https://your-domain.atlassian.net/rest/api/3/issue/10002
assignee: Pat Smith
created: 2026-07-10T08:00:00-05:00
updated: 2026-07-20T16:00:00-05:00

## Description
Fix the order flow

## Acceptance criteria
...
```

**Issue comments** — file named `{issue-key}-comment-{comment-id}.md`. Webhooks: `comment_created`, `comment_updated`, `comment_deleted`.

```markdown
id: 10000
url: https://your-domain.atlassian.net/rest/api/3/issue/10010/comment/10000
author: Pat Smith
created: 2026-07-20T16:00:00-05:00

Lorem ipsum dolor sit amet, consectetur adipiscing elit.
```

## Not yet built: adapter-era skills

The shipped skills (`skills/` at the repo root, an installable Claude Code plugin: `ingest`,
`query`, `lint`, `source-update`, `maintain`) target today's adapter-less, git-history-backed CLI —
see [implementation-history.md](implementation-history.md) and [ADR-0008 through ADR-0010](../adr/)
for what was built and why it diverges from `source-update`'s design below, which assumes adapters
exist:

**source-update** (adapter-era design, not what shipped) — separate from `ingest` because the
judgment calls differ: matching identity, computing a delta, and deciding whether that delta is
safe to fold in automatically. Triggered by a source-system event (Jira webhook, GitHub event) or
manual invocation:

1. Extract `stable_id` via the adapter. If `None`, stop — flag for manual filing, do not proceed.
2. Look up the Raw source manifest for an existing entry with that `stable_id`.
   - Not found → hand off to `ingest` (this is a first-time source).
   - Found → `fetch` current state, `diff` against last-known snapshot.
3. For `new_comment_ids` in the delta: write the new comment snapshot unit(s), invoke `ingest`
   scoped to just the new material, open a PR the same way a routine ingest would (see "Write
   gate").
4. For `changed_fields` in the delta: write the new field-state snapshot version, then open a PR
   same as step 3 — but the PR description must explicitly flag which prior wiki claims may now be
   stale ("underlying ticket status changed from X to Y — verify affected pages still hold"),
   rather than presenting it as a routine update. The distinction between comments and field edits
   is in how confidently the PR is framed, not whether a PR exists — see "Write gate."
5. Append an entry to `log.md` citing the source and summarizing the delta.

This means the "auto re-ingest vs. flag for review" split (per mutation type) was never meant to be
a split between "PR" and "no PR" — it's a split in how the resulting PR is framed:

- Comment-driven updates: PR reads like a normal ingest PR.
- Field-edit-driven updates: PR is explicitly labeled/described as needing extra scrutiny, since
  the underlying source may have invalidated something already written, not just added to it.

## Testing strategy

Two required layers, following from the thin-CLI architectural constraint:

- **Unit tests** on internal functions: source classification (new/update/duplicate), delta
  computation, frontmatter diffing, etc. — where real coverage lives.
- **CLI-invocation tests** via `click.testing.CliRunner`: assert each command parses args correctly,
  calls the right internal function, and produces the right exit code/output. No re-testing of
  business logic already unit-tested.
- No golden-file byte-diff comparisons against `catalog.jsonl`/`log.jsonl` — structured assertions
  on parsed output instead.

**`source-delta` fixture uses real git**: a pytest fixture inits a throwaway repo in `tmp_path`,
commits an initial source-file version ("last known"), then mutates the file on disk uncommitted
("current"). Exercises real `git log`/`git show`, including the no-prior-commit and shallow-clone
edge cases.

**Fixture strategy**: per-command isolated fixtures via a shared factory helper (e.g.
`make_source(tmp_path, source, status=..., ...)`) — not one shared "golden wiki" repo.

**Definition of Done**:
- Every command above has (a) unit test coverage for its internal logic, (b) a `CliRunner` adapter
  test verifying delegation/exit codes/output.
- `mypy`, `ruff`, and pre-commit all pass clean.
- `doctor` run against a real fixture repo state passes.
