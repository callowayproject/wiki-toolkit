# Ingest Prompt Templates

These are the mental frameworks to use when distilling a source into wiki pages.

## Knowledge Extraction Frame

When reading a source document, ask yourself:

1. **What are the 3-5 most important ideas in this document?**
   These become concept pages or updates to existing concept pages.

2. **Who or what is mentioned that deserves its own page?**
   People, tools, organizations, projects → entity pages.

3. **What does this document teach you how to do?**
   Procedures, workflows, techniques → skills pages.

4. **What claims does this document make?**
   Each claim needs a source attribution.
   If it contradicts an existing wiki claim, note the contradiction.

5. **How does this connect to what the wiki already knows?**
   This is the most important question.
   The value of the wiki compounds through connections.

## Paper Extraction Frame

For academic papers the generic frame above misses what makes a paper legible.
Add these questions:

1. **What problem does it solve, and what's new?**
   The one-sentence thesis + the single most important result.
2. **What is the method?**
   Which figure shows the architecture/pipeline?
   Sketch it as a Mermaid flowchart — capture the data flow, not just the component names.
3. **What are the core equations?**
   The 1–3 that define the mechanism — keep them as math (`$$…$$`), not prose.
4. **What's the experimental setup and the headline numbers?**
   Datasets, baselines, and the metric table the paper is judged on.
5. **What are the ablations and limitations?**
   What did they vary, and what does the method _not_ do?

These map onto the Paper Deep-Dive Template in `llm-wiki/SKILL.md`.
The goal is a page a reader could study instead of the PDF; figures, equations, and results included.

## Synthesis Frame

When a new source covers ground that existing pages already cover:

- Don't duplicate — synthesize
- If the new source agrees with existing content, strengthen the claims with additional attribution
- If it disagrees, create an "Open Questions" or "Debate" section noting both positions
- If it adds nuance, weave it into the existing narrative

## Cross-Reference Discovery

After extracting knowledge, look for these connection patterns:

- **Is-a**: "Transformers are a type of neural network" → link from transformer page to neural-network page
- **Uses**: "RLHF uses reward models" → link from RLHF to reward-models
- **Contrasts-with**: "CNNs vs. Transformers for vision" → mutual links
- **Part-of**: "Attention is a component of transformers" → link from attention to transformers
- **Created-by**: "Transformers were introduced by Vaswani et al." → link to entity page
- **Applied-in**: "Transformers are used in GPT" → link from transformers to GPT

## Confidence Markers

Every claim starts as a faithful paraphrase (extracted, unmarked).
Ask yourself, for each claim you write:

- **Did the source say this, or did I connect the dots?**
  If you're the one drawing the connection — the source never states it directly — mark it `^[inferred]`.
  > RLHF and constitutional AI both shape model behavior post-pretraining. ^[inferred]
- **Do my sources disagree, or is one of them unclear on this point?**
  Mark it `^[ambiguous]` instead of silently picking a side.
  > The team disagrees on whether the migration caused the latency regression. ^[ambiguous]
- **Does this claim also need a source citation?**
  Stack the confidence marker first, the source citation second — they're independent suffixes.
  > The retry queue was added to absorb the Q3 traffic spike. ^[inferred]^[incident-report-14]

Don't hand-compute the page-level `confidence:` rollup by guessing — count your bullets
(or paragraphs, if the page has no bullets),
tally how many carry each marker, divide by the total, and round to 2 decimals, round-half-up
(a tie like 0.125 rounds to 0.13, not 0.12).
If you didn't track this carefully while writing,
leave `confidence:` off the page rather than write a number `lint` will flag as drifted.

## Typed Relationships

Once a page has its `[[wikilink]]`s, look at each one and ask:
**is the relationship between these two pages more specific than "related"?**
If the source material makes it clear, add a `relationships:` entry describing it from this page's point of view —
don't add a link that isn't already in the body, and don't add an entry when the source is vague about direction.

```yaml
relationships:
  - target: "[[Reward Modeling]]"
    type: uses          # this page's approach uses reward modeling
  - target: "[[Legacy Auth Middleware]]"
    type: replaces       # this page's approach replaces the old one
  - target: "[[Constitutional AI]]"
    type: related_to     # connected, but the source doesn't specify how
```

Type cheat sheet (always from the declaring page's perspective):

- `extends` — this page builds on the target's ideas without replacing them
- `implements` — this page is a concrete realization of the target's design
- `contradicts` — this page's claims conflict with the target's
- `derived_from` — this page's content was distilled from the target
- `uses` — this page's subject depends on or invokes the target's
- `replaces` — this page's subject supersedes the target's
- `related_to` — connected, but none of the above fit or the source doesn't say

When in doubt between a specific type and `related_to`, take `related_to` — or skip the entry.
A fabricated `extends` is worse than no relationship at all.
