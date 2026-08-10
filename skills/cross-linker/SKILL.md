---
name: cross-linker
description: Weave a wiki page into the rest of the wiki's knowledge graph by scoring and applying cross-references, then inferring the relationship each one represents. Use once per `ingest` session, between `build` and `lint` — not standalone, and not for `source-update`.
---

# cross-linker

Find the links an `ingest` session's own pages should have to the rest of the
wiki, and add the high-confidence ones. Scoring, placement, and relationship
inference are agent judgment; finding literal mentions is not — that part is
a deterministic CLI call.

Runs once per session, over every page the session wrote or updated — never
a full-vault rescan, and never once per batch in a batch-dispatched session.

## Sequence

1. **`wiki-toolkit cross-link-candidates <page> [<page> ...]`**
   Pass every page path the session wrote or updated (the same set going to
   `log`/`propose-pr`). Emits one JSON candidate per line —
   `{page, target, mention_text, match_type}` — for each literal,
   case-insensitive title/alias mention of another catalog entry found in
   those pages' bodies. `match_type` is `title` or `alias`. This is the only
   full-vault-scale step; it reads `catalog.jsonl`, not every page body.

2. **Score every candidate**, plus any pair the CLI didn't surface (a page
   and a catalog entry that share `sources:` entries, tags, or an outbound
   `[[wikilink]]` but no textual mention). Read a target page's frontmatter
   only when scoring needs it (shared tags). In a manual session you
   already have the session's own pages' content from step 2 of `ingest` —
   don't re-read them. In a batch-dispatched session the coordinator never
   read subagent-drafted pages into its own context (they were moved
   straight from `docs/_staging/` to `docs/wiki/`), so read each session
   page's body here before scoring or placing links against it.

   | Signal | Points | Source |
   |---|---|---|
   | Exact title/alias match in body | +4 | a `cross-link-candidates` hit |
   | Partial name match (substring, not a full mention) | +1 | your own read of the body |
   | Shared `sources:` entries | +2 | session page's `sources:` vs. target's catalog entry |
   | Tag overlap | +2 | session page's `tags:` vs. target page's `tags:` frontmatter |
   | Co-citation (shared outbound link) | +2 | session page's `links` vs. target's `links` in `catalog.jsonl` |

   Sum every signal that applies to a given (page, target) pair.

3. **Tier by score:**
   - **≥ 6 — EXTRACTED**: apply inline.
   - **3–5 — INFERRED**: apply inline if a natural mention exists, else add
     to a `## Related` section. Report either way.
   - **1–2 — AMBIGUOUS**: skip. Report only — no link, no relationship
     entry.

4. **Place EXTRACTED/INFERRED links:**
   - **Inline (preferred)**: wrap the first natural mention in the page body
     in `[[target|display text]]` (use the `|display text` form when the
     wikilink path differs from the mention text). Don't double-link a
     target that already has a `[[wikilink]]` on the page.
   - **`## Related` (fallback)**: when there's no natural in-body mention
     (e.g. a shared-tag-only INFERRED candidate), add a bullet to a
     `## Related` section at the bottom of the page — `- [[target]] — why`.
     Append to an existing `## Related` section rather than creating a
     second one; don't duplicate an existing entry.

5. **Infer a relationship type** for every link just added (EXTRACTED or
   INFERRED only — AMBIGUOUS candidates get no relationship entry, no type
   inference at all). Scan the sentence containing the mention (for a
   `## Related` link, the shared-tag/source context instead) against this
   fixed table, first match in table order wins:

   | Sentence pattern | Inferred type |
   |---|---|
   | "X extends / builds on / generalises Y" | `extends` |
   | "X implements / is an implementation of Y" | `implements` |
   | "X contradicts / opposes / refutes / is at odds with Y" | `contradicts` |
   | "X is derived from / based on / adapted from Y" | `derived_from` |
   | "X uses / relies on / depends on / requires Y" | `uses` |
   | "X replaces / supersedes / deprecates Y" | `replaces` |
   | No match, or a shared-tag-only match with no in-body mention | `related_to` |

   Write `{target: "[[target]]", type: "..."}` to the page's `relationships:`
   frontmatter (add the block if absent, after `aliases:` or `tags:`).
   Append only — never touch a `relationships:` entry that predates this
   run, and never duplicate a target already listed. A `relationships:`
   entry only ever enriches a link that already exists as a `[[wikilink]]`
   on the same page (inline or in `## Related`) — never write one for a
   target with no corresponding wikilink.

6. **Report**, conversationally, in-session — no persisted file. For each
   page with links added: how many, at what confidence tier, where placed
   (inline vs. `## Related`), and what relationship types were inferred.
   List AMBIGUOUS candidates too, skipped, so a human can add them by hand
   if they disagree.

7. **`wiki-toolkit log --action ingest --title "..." --details "..."`**
   Once per page that had links added, describing what was linked. Reuses
   `ingest`'s existing log action — cross-linker's edits ride in the same
   commit as the rest of the session.

## Rules

- Scope to the session's own pages as sources. Every other catalog entry is
  a link *target* only — never re-scanned as a source of new candidates.
- Never fabricate a relationship type: if the sentence context is genuinely
  ambiguous, use `related_to` rather than guessing a specific type.
- Never add a `relationships:` entry without a corresponding `[[wikilink]]`
  on the same page.
- Skip AMBIGUOUS candidates entirely — no link, no relationship entry, just
  a report line.
- One cross-linker pass per `ingest` session, after `build` and before
  `lint` — regardless of how many pages or sources the session covers, and
  regardless of how many batches a batch-dispatched session ran.
