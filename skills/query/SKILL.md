---
name: query
description: Search the wiki_toolkit catalog with `wiki-toolkit search-catalog` and answer questions with citations to the matched pages. Use when the user asks "what do we know about X", "search the wiki for X", or any question that should be answered from the docs/wiki/ catalog rather than from memory.
---

# query

Answer questions from the wiki, not from memory. Answering is read-only; only
fall through to the write gate when the answer synthesizes something new.

## Sequence

1. **`wiki-toolkit search-catalog --query "..."`**
   Searches `docs/catalog.jsonl` by title and path. Try a few phrasings if
   the first query returns no matches — the search is literal text matching,
   not semantic.

2. **Read the matched pages** under `docs/wiki/` and answer the question
   using their content. Cite the page(s) you drew from (path and title) so
   the user can verify the claim.

3. **If the answer is just what's already on the matched pages, stop.**
   Answering alone is never a write — do not run `build`, `lint`, `log`, or
   `propose-pr` for a plain lookup.

4. **If synthesizing the answer produced new knowledge** (a connection
   across pages, a conclusion not written down anywhere), file it back
   through the same write gate `ingest` uses, in order:
   - Write the synthesis as a new or updated page in `docs/wiki/`, following
     `docs/schema.md` (frontmatter, `source_count`, ≥2 outbound
     `[[wikilink]]`s, cite the pages it draws from as `sources`).
   - `wiki-toolkit build`
   - `wiki-toolkit lint` — fix any violations, re-run until clean.
   - `wiki-toolkit log --action ingest --title "..." --details "..."`
   - `wiki-toolkit propose-pr --pages <path> --frame routine`

## Rules

- Never invent an answer when `search-catalog` returns no matches — say so,
  don't guess.
- A synthesis that gets written back must cite the pages it came from, same
  as any other source.
