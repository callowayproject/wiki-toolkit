# LLM Wiki Toolkit — Spec

Specifies the AI skills and helper tools that implement [llm-wiki.md](Reference/llm-wiki.md) as a general-purpose toolkit.
An AI Agent harness operates this toolkit; the toolkit itself is domain-agnostic.

## Wiki structure
The basic layout of the wiki is:

```text
repo-root/
└── docs/
    ├── .agents/
    │   └── skills/            # The AI Agent skills required to manage
    ├── catalog.jsonl          # Catalog of everything in the wiki
    ├── log.jsonl              # Chronological listing of wiki events
    ├── schema.md              # Evolving description of the wiki
    ├── source-manifest.jsonl  # Index of sources, where they are linked
    ├── sources/               # Raw sources
    └── wiki/
```

### Sources

There are two kinds of sources:

**Version-controlled:** (source code, PRs) These are never copied into `sources/`. Git already has an immutable history; duplicating it into `sources/` is pure redundancy. An entry for each file is maintained in the `catalog.jsonl` file.

**Snapshot:** (Jira, Slack, external wiki pages) A snapshot is anything external to the source repository. Markdown versioned snapshots of the content are copied into `sources/`, because the toolkit has to create the history the source system doesn't provide.

A source type must expose a stable external ID (e.g., a URI, Jira ticket key, Slack permalink, or Confluence page ID) to be eligible for snapshot handling. If a source type can't supply one, the toolkit refuses automatic ingestion and flags it for manual filing. Fuzzy content-matching is deliberately excluded as a dedup mechanism, since a false-positive merge in an unattended, write-capable agent is worse than a missed source.

Within a snapshot source, two mutation types are handled differently:

- **Comments:** Each comment on a source is treated as its own source. Each comment has its own stable ID from the source system. No diffing: the toolkit tracks the highest processed comment ID per parent source and treats anything newer as new.
- **Field edits:** Changes to sources (status, description, assignee, etc.) mutate in place. The toolkit diffs the full field state against the last snapshot to produce a delta of fields that have changed.

#### Source frontmatter

Each source should have the following frontmatter prepended to it:

- **source_id:** Required unique identifier for this source. A URI is recommended
- **processed:** Defaults to `false` to indicate it hasn't been processed by the toolkit/AI Agent

### Source manifest

The source manifest (`source-manifest.jsonl`) is an index of all sources referenced in the wiki. The toolkit will use it to determine the potential scope of a change.

#### Source manifest schema

- `source_id`: The unique identifier for this document
- `path`: The relative path to the document from the repo root.
- `title`: The title of the document or the file name, if necessary.
- `referenced_by`: A list of relative paths to wiki documents that reference this file.
- `updated`: The ISO-8601 date-time string when it was updated.
- `update_sha`: The SHA hash of the Git commit last processed for this file or the computed SHA hash of files for mutable sources, like Jira tickets.
- `status`: `proposed` or `resolved`. `proposed` means the source was ingested ahead of any code change (a design doc, a ticket) and its wiki page is speculative; `resolved` means a PR has since referenced this source, confirming it against an actual diff.

### Catalog

The catalog (`catalog.jsonl`) is an index of all the documents in the wiki (`wiki/`), with cross-references to the sources they reference.

#### Catalog schema

- `path`: The relative path to the document from the repo root.
- `title`: The title of the document.
- `sources`: A list of sources (`source_id`s) this document references.
- `updated`: The ISO-8601 date-time string when it was updated.
- `status`: `resolved` when all sources have a `status` of `resolved`. `proposed` if any source has a `status` of `proposed`.

### Log

The log (`log.jsonl`) is an append-only chronological list of wiki events.

#### Log schema

- `date`: The ISO-8601 date-time string when it was created.
- `action`: The type of event being logged. One of `ingest`,  `update`, `lint`, `create`, `archive`,  `delete`.
- `message`: A one-line message summarizing the action.
- `details`: Details about the action.

### Schema

The schema (`schema.md`) provides instructions to the AI agent on how to manage this wiki. The AI agent can modify it

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

## Wiki Document Frontmatter
  ```yaml
  ---
  title: Page Title
  created: YYYY-MM-DD
  updated: YYYY-MM-DD
  tags: [from taxonomy below]
  sources: [source_id]
  status: resolved  # or `proposed` for speculative pages ingested ahead of any code change
  ---
  ```

## Tag Taxonomy

Rule: every tag on a page must appear in this taxonomy. If a new tag is needed, add it here first, then use it. This prevents tag sprawl.

- <example tag>
- <another tag>

````


## Adapter interface

Each source type (GitHub, Jira, ...) implements:

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

### v1 adapters

- **GitHub** — issues, PRs, Renovate PRs. Already the trigger mechanism per `idea.md`. Dependabot PRs are out of scope for the pilot (see `idea.md` Solution section).
- **Jira** — the concrete comment-chain case that motivated this spec.
- **Confluence** — design docs. `stable_id` is the Confluence page ID. Ingesting a design doc ahead of any PR produces a `status: proposed` wiki page (see "Write gate" and `idea.md`'s source-manifest schema); a later PR that references the same page ID resolves it via the normal source-linkage flow, flipping `status` to `resolved`.

Everything else named in `idea.md`'s "Possible sources" list (Slack, Teams, Azure DevOps, Linear) implements this interface later. No stub code is required now — the interface above is the contract a future adapter must satisfy.

## Skills

Five skills, each a `SKILL.md` for the agent operating the toolkit:

**ingest** — unchanged from `llm-breakdown.md`: take a source (first time seen), read it, write/update wiki pages, cite the source, log it.

**query** — unchanged: search the catalog, read relevant pages, answer with citations, optionally file the answer back as a new page.

**lint** — unchanged: contradictions, staleness, orphan pages, missing cross-references.

**source-update** (new) — separate from `ingest` because the judgment calls differ: matching identity, computing a delta, and deciding whether that delta is safe to fold in automatically. Triggered by a source-system event (Jira webhook, GitHub event) or manual invocation:

1. Extract `stable_id` via the adapter. If `None`, stop — flag for manual filing, do not proceed.
2. Look up the Raw source manifest for an existing entry with that `stable_id`.
   - Not found → hand off to `ingest` (this is a first-time source).
   - Found → `fetch` current state, `diff` against last-known snapshot.
3. For `new_comment_ids` in the delta: write the new comment snapshot unit(s), invoke `ingest` scoped to just the new material, open a PR the same way a routine ingest would (see "Write gate" below).
4. For `changed_fields` in the delta: write the new field-state snapshot version, then open a PR same as step 3 — but the PR description must explicitly flag which prior wiki claims may now be stale ("underlying ticket status changed from X to Y — verify affected pages still hold"), rather than presenting it as a routine update. The distinction between comments and field edits is in how confidently the PR is framed, not whether a PR exists — see "Write gate."
5. Append an entry to `log.md` citing the source and summarizing the delta.

**maintain** — unchanged: periodic sweep invoking `lint`, suggesting new sources/questions to investigate.

## Write gate

Every wiki write goes through a PR — no exceptions, no direct commits, for either LLM-authored content or deterministic tooling output (catalog, index, log). One rule, no second write path to audit.

This means `source-update`'s "auto re-ingest vs. flag for review" split (per mutation type) is **not** a split between "PR" and "no PR" — it's a split in how the resulting PR is framed:

- Comment-driven updates: PR reads like a normal ingest PR.
- Field-edit-driven updates: PR is explicitly labeled/described as needing extra scrutiny, since the underlying source may have invalidated something already written, not just added to it.

## Helper tools (CLI surface)

Extends the `wiki_tool.py` command set from `llm-breakdown.md`:

- `source-match <adapter> <payload>` — resolve `stable_id`, report whether it matches an existing Raw manifest entry (new vs. update).
- `source-delta <adapter> <stable_id>` — fetch current state, diff against last-known snapshot, print the `Delta`.
- `source-snapshot <adapter> <stable_id> --units comments|fields` — write the new Raw snapshot unit(s) for the given mutation type.
- `source-scan` (existing) — skip `version_controlled` source types; they have no Raw file to scan.
- `propose-pr --pages <list> --frame routine|needs-review` — branch, commit, open PR, with the description framing set per the mutation type that triggered it.
