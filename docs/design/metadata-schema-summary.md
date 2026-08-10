# Metadata schema — confidence markers & typed relationships — summary for spec

Handoff note for a future session to write the formal "Spec:" issue (same shape as
[Spec: batched multi-source ingest, issue #100](https://github.com/callowayproject/wiki-toolkit/issues/100),
which came out of the [batching map](https://github.com/callowayproject/wiki-toolkit/issues/84)).
All decisions below are final — the source map,
[Metadata schema map, issue #88](https://github.com/callowayproject/wiki-toolkit/issues/88), is fully resolved:
all 5 child tickets closed 2026-08-10.

## Problem statement

Wiki pages mix paraphrased fact, LLM-synthesized inference, and disputed/unclear claims with no
inline way to tell them apart — a reader can't scan a page for "how much of this did the LLM make
up." Separately, `[[wikilinks]]` between pages carry no semantic weight: "related to" is all a link
ever says, never *how* two pages relate. Both gaps come from the same source idea doc
([docs/design/batching-and-crosslink.md](batching-and-crosslink.md), `## Additional metadata`
section) and both need a schema (not a detection mechanism) before any skill can start writing
these fields.

## Solution

Two additive, optional frontmatter/inline features, purely schema + validation — no
inference/detection heuristics (that's the [cross-linker map, issue #94](https://github.com/callowayproject/wiki-toolkit/issues/94)'s job), no migration of existing pages, and touching only `ingest` (writer) and `lint`
(validator), not query/search or maintain.

### 1. Confidence marker

Renamed from the source doc's "provenance marker" — collided with `CONTEXT.md`'s pre-existing
"Provenance marker" (the unrelated `.provenance` skill-copy drift-detection file). See
[issue #89](https://github.com/callowayproject/wiki-toolkit/issues/89).

- Three states, unchanged from the source doc: **extracted** (default, no marker — a paraphrase of
  what a source actually says), **inferred** (`^[inferred]` suffix — an LLM-synthesized connection
  the source doesn't state directly), **ambiguous** (`^[ambiguous]` suffix — sources disagree or
  are unclear).
- Stacks with the existing `^[source_id]` footnote citation as an independent suffix, confidence
  marker first: `^[inferred]^[design-doc-3]` ([issue #90](https://github.com/callowayproject/wiki-toolkit/issues/90)).
- Optional page-level rollup in frontmatter:
  ```yaml
  confidence:
    extracted: 0.72
    inferred: 0.25
    ambiguous: 0.03
  ```
  Written best-effort by `ingest`. `lint` recomputes and flags drift — same recompute-and-flag-drift
  pattern as `source_count`: counts one unit per bullet (or per paragraph on non-bulleted pages),
  rounds to 2 decimal places round-half-up, flags on any mismatch after rounding (no tolerance band)
  ([issue #93](https://github.com/callowayproject/wiki-toolkit/issues/93)).

### 2. Typed relationships

```yaml
relationships:
  - target: "[[Transformer Architecture]]"
    type: extends
  - target: "[[LSTM]]"
    type: contradicts
```

- `type` is a **fixed 7-value enum**, not a per-wiki extensible list like Tag Taxonomy — all 7
  source-doc types adopted as-is (`extends`, `implements`, `contradicts`, `derived_from`, `uses`,
  `replaces`, `related_to`), each with a meaning + example in `toolkit-spec.md`'s new "Relationship
  Types" table. Fixed so edges stay comparable across wikis ([issue #91](https://github.com/callowayproject/wiki-toolkit/issues/91)).
- Rules (unchanged from the source doc): optional, omit entirely if unknown; enriches an existing
  `[[wikilink]]` rather than duplicating it; direction is from this page's own perspective only;
  don't fabricate — use `related_to` or omit when the source material doesn't make direction/type
  clear.
- `lint` verifies `target` resolves to an existing page, reusing the resolution rule already used
  for missing-cross-reference detection on body wikilinks. A broken target is **flagged, not
  rejected** — the write gate's PR review is the actual enforcement point, matching `lint`'s
  existing role as a reporting tool, not a hard gate ([issue #92](https://github.com/callowayproject/wiki-toolkit/issues/92)).

## Where the schema lives

All of the above is already written into `docs/design/toolkit-spec.md`'s Schema section
(Conventions list, Wiki Document Frontmatter block, new Relationship Types table) and into
`CONTEXT.md`'s glossary (new "Confidence marker" entry, symmetric `_Avoid_` cross-reference added
to the existing "Provenance marker" entry). A spec-writing session should treat those files as the
source of truth for exact wording — this document is a pointer + rationale summary, not a
restatement to keep in sync.

## Testing-relevant behavior (for a future spec's Testing Decisions section)

- `lint` drift check on `confidence:`: given a page with N bullets/paragraphs and known marker
  counts, the recomputed fractions (2 decimals, round-half-up) must exactly match the frontmatter
  values or `lint` flags it.
- `lint` target check on `relationships:`: given a page with a `relationships:` entry whose `target`
  doesn't resolve to any existing page, `lint` flags it without failing the run.
- Both `ingest` writes (best-effort `confidence:` rollup) and `lint` checks are additive — a page
  with neither field must lint clean exactly as it does today.

## Still open (not blocking a spec)

- Whether confidence markers apply inside non-prose content (code blocks, tables) — left in the
  map's "Not yet specified" as fog, not yet sharp enough to ticket.
- How `relationships:` interacts with misc-page affinity/promotion scoring — explicitly out of
  scope for this map, belongs to the [cross-linker map, issue #94](https://github.com/callowayproject/wiki-toolkit/issues/94).
