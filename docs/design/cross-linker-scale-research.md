# Research: prior art on cross-linking / link-suggestion at scale

Ticket: #97 (child of Cross-linker skill spec map, #94)

Feeds into: [cross-linker-spec.md](cross-linker-spec.md) — this research's two follow-ups
(incremental scan, literal-string pre-filter) aren't yet folded into that spec.

## Question

Does the toolkit's existing frontmatter-registry + selective-full-read pattern
(from `Reference/llm-wiki.md`'s "index.md is content-oriented...
avoids the need for embedding-based RAG infrastructure" primitive) hold up as
the scale strategy for `cross-linker`, or does prior art suggest something
meaningfully better?

## Prior art surveyed

- **Obsidian "Smart Connections"** — embedding-based link suggestion.
  Confirms the frontmatter-registry pattern's underlying assumption: it
  re-embeds only *changed* notes on save (event-driven incremental update),
  not the whole vault each run. Full re-embed only happens once, at initial
  install. Initial full-vault indexing cost scales roughly linearly (~2 min
  per 1K notes on decent hardware) — i.e. even the embedding-heavy approach
  treats "rescan everything" as a one-time cost, not a steady-state one.
- **Roam Research / Logseq "unlinked references"** — not embedding-based at
  all. It's literal substring/title matching: each page title is scanned
  against block text via the app's maintained block-level index (Datalog DB
  in Roam, DataScript in Logseq), not a fresh full-text pass over raw files.
  Candidate generation is a plain string match; no ranking model needed
  because exact title occurrence is treated as sufficient signal for a
  suggestion.
- **Docs linters (Vale, markdown-link-check, mkdocs)** — cheap because they're
  not LLM-token-metered, but the transferable idea is uniform: they scope
  work to files touched since the last run (git diff / mtime), not the whole
  tree, every run.
- **RAG / embedding-based relation suggestion** — the standard shape is
  candidate generation (cheap, high-recall) → rerank (expensive, high-
  precision). This is structurally identical to what the toolkit's
  frontmatter-registry → selective-Read pattern already does; frontmatter
  summaries/tags stand in for embeddings as the cheap candidate filter, and
  the LLM's full-body read + judgment stands in for the reranker.

## Verdict

The frontmatter-registry + selective-read pattern is the right shape and
doesn't need to be replaced. At wiki scale (hundreds, not millions, of
pages) it's a reasonable, infrastructure-free substitute for an embedding
index — this matches the toolkit's existing bias against fuzzy-matching
infra. Two concrete gaps are worth a follow-up design ticket, both drawn
directly from the prior art above:

1. **Incremental scan, not full-registry rescan, per run.** Every surveyed
   tool (Smart Connections' event-driven re-embed, docs linters' mtime/diff
   scoping) treats "reprocess everything" as a one-time cost, not a
   steady-state one — but cross-linker currently has no such boundary
   specified. Concrete hook: `catalog.jsonl` already carries an `updated`
   field per page. A cross-linker run should diff against its own last-run
   timestamp (or a `.cross-linker-state` marker) and only treat pages with
   `updated` newer than that marker as new candidates needing outbound-link
   scanning — existing pages only get pulled in as potential *targets* found
   via the frontmatter registry, not rescanned as sources.
2. **A cheap non-LLM pre-filter beyond frontmatter, borrowed from Roam/
   Logseq's unlinked-references mechanism**: a literal-string grep
   (`grep -l -F "<page title>"` / ripgrep) for other pages' exact titles and
   aliases across body text, run before any LLM `Read` call. This costs zero
   LLM tokens (it's a shell op, not a context read) and directly produces
   high-confidence EXTRACTED-tier candidates (exact title mention = strong
   signal), narrowing what needs a full-body `Read` + LLM judgment call to
   the INFERRED/AMBIGUOUS tier only — pages with topical/tag overlap in the
   frontmatter registry but no literal string hit.

Neither of these requires new infrastructure (no vector DB, no fuzzy
matching) — both fit the toolkit's existing "stable ID / cheap primitive
first" design bias. Recommend the follow-up grilling ticket decide: (a)
where the last-run marker lives, and (b) whether the grep pre-filter runs
against page titles only or titles+aliases from frontmatter.

## Sources

- https://github.com/brianpetro/obsidian-smart-connections
- https://smartconnections.app/smart-connections/
- https://starlog.is/articles/data-knowledge/brianpetro-obsidian-smart-connections
- https://discuss.logseq.com/t/unlinked-reference-finder/4510
- https://discuss.logseq.com/t/have-you-ever-designed-for-unlinked-references/19896
