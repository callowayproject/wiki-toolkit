# wiki-toolkit

Domain glossary for the `wiki_toolkit` CLI — the deterministic tooling that ingests pre-materialized Markdown sources into an LLM-Wiki and keeps it in sync.

## Language

**source**:
The identity field on a Raw source file's frontmatter, and the general term for one unit of external input (a design doc, a ticket, a comment) tracked by the toolkit. In v1, this is the only identity concept — there is no separate adapter-level `stable_id` distinct from it, since v1 has no adapters.
_Avoid_: source_id, stable_id (both are pre-v1/adapter-era terms; don't use once adapters exist without redefining the relationship to `source`)

**Snapshot source**:
A source type with no version history of its own (Jira, Slack, Confluence). Its content is copied into `sources/` as Markdown because the toolkit must create the history the source system doesn't provide.
_Avoid_: "snapshot" alone when referring to the source type — pair it with "source" to distinguish from a last-known revision.

**Last-known revision**:
The prior commit on `main` for a given Raw source file's path — the baseline `source-delta` diffs the current fetched state against. Git history is the storage mechanism; there is no separate revision store. First-time ingestion diffs against a synthetic empty baseline.
_Avoid_: snapshot (reserved for the source-type sense above), commit (that's git's term for the mechanism, not our domain concept for the baseline)

**Processed** (source state):
A source file the toolkit has scanned via `source-scan` and found to be neither a duplicate nor an error. Set only by the CLI, never by upstream materializers. Independent of whether any wiki note yet cites it.

**Covered** (source state):
A source that at least one Wiki note's `sources:` frontmatter references (tracked as `covered_by` in the source manifest). A source can be `processed` but not yet `covered` — that's an expected transient state, not an error; `source-lint` flags sources stuck in it as a backlog signal, not enforced at scan time.
