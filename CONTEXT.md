# wiki-toolkit

Domain glossary for the `wiki_toolkit` CLI —
the deterministic tooling that ingests pre-materialized Markdown sources into an LLM-Wiki and keeps it in sync.

## Language

**source**: The identity field on a Raw source file's frontmatter, and the general term for one unit of external input
(a design doc, a ticket, a comment) tracked by the toolkit.
In v1, this is the only identity concept — there is no separate adapter-level `stable_id` distinct from it,
since v1 has no adapters.
_Avoid_: source_id, stable_id (both are pre-v1/adapter-era terms;
don't use once adapters exist without redefining the relationship to `source`)

**Batch**: A group of raw files under a `source_dir`, sized to a byte/file cap
for parallel `wiki-ingest` dispatch (`batch-plan`).
Not a `source`-domain concept: batching runs over plain files before any of them has frontmatter, an identity,
or a manifest entry — it's an ingest-dispatch mechanic, not a source lifecycle state.
_Avoid_: using "batch" to mean a group of sources once processed — a batch is pre-ingest file grouping only.

**Snapshot source**: A source type with no version history of its own (Jira, Slack, Confluence).
Its content is copied into `sources/` as Markdown
because the toolkit must create the history the source system doesn't provide.
_Avoid_: "snapshot" alone when referring to the source type —
pair it with "source" to distinguish from a last-known revision.

**Last-known revision**: The prior commit on `main` for a given Raw source file's path —
the baseline `source-delta` diffs the current fetched state against.
Git history is the storage mechanism; there is no separate revision store.
First-time ingestion diffs against a synthetic empty baseline.
_Avoid_: snapshot (reserved for the source-type sense above), commit
(that's git's term for the mechanism, not our domain concept for the baseline)

**Processed** (source state): A source file the toolkit has scanned via `source-scan`
and found to be neither a duplicate nor an error.
Set only by the CLI, never by upstream materializers.
Independent of whether any wiki note yet cites it.

**Covered** (source state): A source that at least one Wiki note's `sources:` frontmatter references
(tracked as `covered_by` in the source manifest).
A source can be `processed` but not yet `covered` — that's an expected transient state, not an error;
`source-lint` flags sources stuck in it as a backlog signal, not enforced at scan time.

**Local skill copy**: The versioned copy of the five agent-facing `SKILL.md` files
that `init` scaffolds into a consumer wiki's `docs/.agents/skills/`, distinct from the installable Claude Code plugin
(`skills/` at this repo's root) it was copied from.
Exists so a wiki is self-contained without a live runtime dependency on the plugin.
_Avoid_: "the skills" alone when the distinction between the plugin and this copy matters (e.g. discussing drift).

**Provenance marker**: `docs/.agents/skills/.provenance` —
records the `wiki_toolkit` package version a local skill copy was scaffolded from.
`doctor` compares it to the installed package version to detect drift; only `init` writes it.
_Avoid_: confidence marker (different concept — see Confidence marker entry)

**Confidence marker**: A per-claim epistemic tag on wiki page content: **extracted**
(default, no marker — a paraphrase of what a source actually says),
**inferred** (`^[inferred]` suffix — an LLM-synthesized connection or implication the source doesn't state directly),
or **ambiguous** (`^[ambiguous]` suffix — sources disagree or are unclear).
Optionally rolled up at the page level as a `confidence:` frontmatter block
(best-effort fractions written by `ingest`, recomputed and drift-checked by `lint`).
Exact inline suffix syntax — including interaction with the existing `^[source_id]` footnote convention —
is pinned down separately.
_Avoid_: provenance marker (different concept — see Provenance marker entry)
