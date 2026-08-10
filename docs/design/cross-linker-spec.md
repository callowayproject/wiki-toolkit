# Cross-linker — Skill Spec

Design for the `cross-linker` skill: scan the wiki and automatically discover missing
cross-references between pages. Extracted from `batching-and-crosslink.md` (that file's other
sections — additional metadata, batch planner — were absorbed into
[toolkit-spec.md](toolkit-spec.md) and removed).

Status: active design for the open [cross-linker map, issue #94](https://github.com/callowayproject/wiki-toolkit/issues/94).
Scale strategy: see [cross-linker-scale-research.md](cross-linker-scale-research.md) (issue #97) for the prior-art
survey; the "Scale mechanism" subsection below (issue #115) is the resolved design.

You are weaving the wiki's knowledge graph tighter by finding and inserting missing `[[wikilinks]]` between pages that should reference each other but currently don't.

**Follow the Retrieval Primitives table in `llm-wiki/SKILL.md`.** Build the registry in Step 1 by grepping frontmatter only (not full pages). Reserve full `Read` for the unlinked-mention detection pass, and even there, only read pages whose summaries/titles make them plausible link targets. Blind full-vault reads are what this framework exists to avoid.


## Step 1: Read the catalog

The catalog (`catalog.jsonl`) is an index of all the documents in the wiki (`wiki/`), with cross-references to the sources they reference.

This is your "vocabulary" — every entry in this table is a valid wikilink target. Each entry's `aliases`
field (see toolkit-spec.md's Catalog schema) widens the vocabulary beyond the canonical `title` — an alternate
name a page is also known by.

### Scale mechanism: no full-vault rescan per run

Candidate detection scopes to **this ingest session's pages**, not the whole vault, every run:

- **Sources scanned** — only the pages this ingest session wrote or updated. `cross-link-candidates` takes
  these as explicit path arguments (the same page list the session is about to `log`/`propose-pr`), rather
  than diffing `catalog.jsonl`'s `updated` field against a persisted last-run marker. No state file is needed —
  the session already knows which pages it touched.
- **Targets available** — the full catalog registry (Step 1) stays the match target for those scanned pages;
  existing pages are never rescanned as sources, only looked up as potential link destinations.
- **Zero-token pre-filter** — before any LLM `Read`, `cross-link-candidates` runs a literal `grep -F` match of
  every catalog `title` and `aliases` entry against the session's page bodies. This produces the high-confidence
  EXTRACTED-tier candidates cheaply; only pages with a hit (or with tag/`sources:` overlap feeding the
  INFERRED tier per #96) need a full-body `Read` for scoring and relationship-type inference.

## Step 2: Scan for Missing Links

For each page in the vault:

1. **Read the full content**
2. **Extract existing wikilinks** — find all `[[...]]` references already present
3. **Search for unlinked mentions** — check if the page's text contains any of these, without being wrapped in `[[...]]`:
   - Page filenames (e.g., the word "MyProject" appears but `[[projects/my-project/my-project]]` is missing)
   - Page titles from frontmatter
   - Aliases from frontmatter
   - Entity names, project names, concept names from the registry

4. **Check for semantic connections** — pages that share multiple tags or are in the same project directory but don't link to each other

### Matching Rules

- **Case-insensitive matching** for names (e.g., "my-project" matches page `MyProject`)
- **Diacritic-insensitive matching** — normalize both the page name and the body text with Unicode NFKD (decompose accented characters to base + combining marks, strip combining marks) before comparing. This ensures body text "Muller" matches page `[[entities/müller]]` and vice versa.
- **Skip self-references** — a page shouldn't link to itself
- **Skip common words** — don't link "the", "and", generic terms. Only match on distinctive names
- **Prefer the shortest unambiguous wikilink path** — use `[[page-name]]` not `[[full/path/to/page-name]]` when the name is unique across the vault
- **Don't link inside code blocks** or frontmatter
- **Don't double-link** — if `[[foo]]` already appears on the page, don't add another

## Step 3: Score and Rank Suggestions

Not every possible link is worth adding. Score each candidate using a composite signal, then tag it with a confidence label.

### Scoring

| Signal                        | Points | Example                                                                                                                                                    |
|-------------------------------|--------|------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Exact name match in text**  | +4     | "MyProject" appears in body text → link to my-project.md                                                                                                   |
| **Shared tags (2+)**          | +2     | Both tagged `#ai #agent` but no link between them                                                                                                          |
| **Same project, no link**     | +2     | Both under `projects/my-project/` but don't reference each other                                                                                           |
| **Mentioned entity/concept**  | +2     | Page mentions "knowledge graphs" → link to `[[concepts/knowledge-graphs]]`                                                                                 |
| **Cross-category connection** | +2     | Source is in `concepts/`, target is in `entities/` (or `skills/` ↔ `synthesis/`) — different knowledge layers make this link more architecturally valuable |
| **Peripheral→hub reach**      | +2     | Source page has ≤ 2 total links (peripheral) but target has ≥ 8 (hub) — connecting a loose page to a load-bearing concept                                  |
| **Partial name match**        | +1     | "graph" appears but page is `knowledge-graphs` — plausible but ambiguous                                                                                   |

### Confidence labels

Tag each candidate with a confidence label based on its score:

| Score | Label         | Action                                                                                                               |
|-------|---------------|----------------------------------------------------------------------------------------------------------------------|
| ≥ 6   | **EXTRACTED** | Link is effectively certain — exact mention or very strong match. Apply inline.                                      |
| 3–5   | **INFERRED**  | Link is a reasonable inference — shared context, cross-category, peripheral→hub. Apply inline or as Related section. |
| 1–2   | **AMBIGUOUS** | Weak or partial match. Skip unless user specifically asks to connect loose pages.                                    |

Only act on **EXTRACTED** and **INFERRED** candidates. Include the confidence label in the Cross-Link Report so the user can review INFERRED links before trusting them.

## Step 4: Apply Links

**Pre-write snapshot** — before the first file write, check whether the vault itself is the root of a Git repository. Merely being a subdirectory of a larger repository does not qualify: running `git add -A` there could capture unrelated files. If the vault is not a standalone Git repository, skip this step silently — no nagging, no suggesting `git init`.

```bash
VAULT_REAL_PATH=$(cd "$OBSIDIAN_VAULT_PATH" && pwd -P)
VAULT_GIT_ROOT=$(git -C "$OBSIDIAN_VAULT_PATH" rev-parse --show-toplevel 2>/dev/null || true)
SNAPSHOT_SHA=""

if [ -n "$VAULT_GIT_ROOT" ] && [ "$VAULT_GIT_ROOT" = "$VAULT_REAL_PATH" ]; then
  if git -C "$OBSIDIAN_VAULT_PATH" diff --quiet \
    && git -C "$OBSIDIAN_VAULT_PATH" diff --cached --quiet \
    && [ -z "$(git -C "$OBSIDIAN_VAULT_PATH" ls-files --others --exclude-standard)" ]; then
    SNAPSHOT_SHA=$(git -C "$OBSIDIAN_VAULT_PATH" rev-parse HEAD)
  else
    if ! git -C "$OBSIDIAN_VAULT_PATH" add -A; then
      echo "Pre-write snapshot failed; abort the skill without writing any vault files." >&2
      exit 1
    fi
    if ! git -C "$OBSIDIAN_VAULT_PATH" commit -m "pre-cross-linker snapshot" --quiet; then
      echo "Pre-write snapshot failed; abort the skill without writing any vault files." >&2
      exit 1
    fi
    SNAPSHOT_SHA=$(git -C "$OBSIDIAN_VAULT_PATH" rev-parse HEAD)
  fi
fi
```

The clean-repository branch deliberately avoids calling `git commit`, so "nothing to commit" is not treated as an error. If `git add` or `git commit` fails, stop before editing the vault; never continue without the promised snapshot.

If `SNAPSHOT_SHA` is non-empty and the skill writes files, include the SHA in the final report. To discard the entire run, after confirming there are no later changes worth keeping, the user can run:

```bash
git -C "$OBSIDIAN_VAULT_PATH" reset --hard "$SNAPSHOT_SHA"
git -C "$OBSIDIAN_VAULT_PATH" clean -fd
```

For each page with missing links:

### 4a: Inline linking (preferred)

Find the first natural mention of the term in the body text and wrap it in wikilinks:

**Before:**
```markdown
This project uses knowledge graphs to connect entities.
```

**After:**
```markdown
This project uses [[concepts/knowledge-graphs|knowledge graphs]] to connect entities.
```

Use the `[[path|display text]]` format when the wikilink path differs from the display text.

### 4b: Related section (fallback)

If the term isn't mentioned naturally in the body but the pages are semantically related (shared tags, same project), add a `## Related` section at the bottom of the page:

```markdown
## Related

- [[projects/my-project/my-project]] — Also uses AI agents for research automation
- [[concepts/knowledge-graphs]] — Core technique used in this project
```

If a `## Related` section already exists, append to it. Don't duplicate existing entries.

### 4c: Infer and write relationship type

For every EXTRACTED or INFERRED link added (inline or related section), infer a semantic relationship type from the surrounding sentence context and write it to the page's `relationships:` frontmatter block. Skip AMBIGUOUS links.

**Type inference rules** — scan the sentence containing the mention (or, for related-section links, the page title and shared-tag context):

| Sentence pattern                                                | Inferred type  |
|-----------------------------------------------------------------|----------------|
| "X extends / builds on / generalises Y"                         | `extends`      |
| "X implements / is an implementation of Y"                      | `implements`   |
| "X contradicts / opposes / refutes / is at odds with Y"         | `contradicts`  |
| "X is derived from / based on / adapted from Y"                 | `derived_from` |
| "X uses / relies on / depends on / requires Y"                  | `uses`         |
| "X replaces / supersedes / deprecates Y"                        | `replaces`     |
| Shared tags or cross-category inference with no directional cue | `related_to`   |

If the surrounding context is ambiguous or the link came from shared-tag matching (no in-body mention), default to `related_to`.

If a sentence matches more than one pattern (e.g. "RAG uses and extends the base retriever"), take the first matching row in table order above — `extends` beats `uses` in that example. Table order is the tie-break; don't add a separate specificity ranking.

Only infer and write a relationship type for EXTRACTED and INFERRED links. AMBIGUOUS links are skipped by Step 3 already — no relationship entry is written for them, and no type is inferred at all.

**Writing the block:**

Read the page's YAML frontmatter. If a `relationships:` block already exists, append new entries without duplicating existing targets. If the block is absent, add it after `aliases:` (or after `tags:` when `aliases:` is missing).

```yaml
relationships:
  - target: "[[concepts/knowledge-graphs]]"
    type: uses
```

Always use wikilink format (`[[path/to/page]]`) for `target` values in the `relationships:` YAML block.

Only add entries for links added in this cross-linker run — do not touch typed entries that were already present.

## Step 5: Score Misc Page Affinity

After the main linking pass, update affinity scores for all pages in `misc/` (pages with `promotion_status: misc` in their frontmatter, or located under the `misc/` directory).

For each misc page:

1. **Collect outgoing links** — all `[[wikilinks]]` in the page body
2. **Collect incoming links** — grep the vault for `[[misc/<slug>]]` and `[[<slug>]]` references
3. For each linked page (both directions), check if it belongs to a project:
   - Lives under `projects/<project-name>/`
   - Has a `project:` frontmatter field matching a project name
4. Group by project name and sum: `outgoing_links + incoming_links`
5. Update the `affinity` frontmatter block on the misc page:

```yaml
affinity:
  obsidian-wiki: 3
  another-project: 1
```

6. If any project's score ≥ 3: flag this page as a **promotion candidate** and record it for the report

**Efficiency note:** only read the full body of misc pages — other pages only need a frontmatter grep to determine their project membership.

## Step 6: Report

Present a summary:

```markdown
## Cross-Link Report

### Links Added: 23 across 12 pages

| Page                                | Links Added | Confidence | Placement           | Relationship Types                 |
|-------------------------------------|-------------|------------|---------------------|------------------------------------|
| `projects/my-project/my-project.md` | 3           | EXTRACTED  | 2 inline, 1 related | uses ×2, related_to ×1             |
| `entities/jane-doe.md`              | 5           | INFERRED   | 3 inline, 2 related | extends ×1, uses ×3, related_to ×1 |
| ...                                 |             |            |                     |                                    |

### Orphan Pages Remaining: 2
- `references/foo.md` — no incoming or outgoing links found
- `concepts/bar.md` — could not find related pages

### Misc Promotion Candidates: N
Pages in misc/ that have ≥ 3 connections to a single project — ready to be promoted:

| Page                                              | Top Project     | Score |
|---------------------------------------------------|-----------------|-------|
| `misc/web-martinfowler-articles-microservices.md` | `obsidian-wiki` | 4     |

To promote: move the page to `projects/<project-name>/references/` and update all backlinks.
```

## Tips

- **Run after every ingest.** New pages are almost always poorly connected. This is the fix.
- **Be conservative with inline links.** Only link the first natural mention, not every occurrence.
- **Don't touch pages in `_archives/` or `_readouts/`.** Archives are frozen snapshots; readouts are derived output from `wiki-narrate`, not knowledge pages.
- **Respect existing structure.** If a page carefully curates its links in a `## Key Concepts` section, add to that section rather than creating a separate `## Related`.
- **Entity pages are link magnets.** An entity like `jane-doe` should be linked from almost every project page. Prioritize these.
