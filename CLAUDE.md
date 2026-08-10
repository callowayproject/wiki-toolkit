# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

`wiki_toolkit` — a CLI plus agent-facing skills that maintain an LLM-Wiki (an
AI-agent-readable infra-documentation set) alongside a codebase, kept in sync
as that codebase changes. The tool has shipped a working v1 (CLI + skills
plugin, see [implementation-history.md](docs/design/implementation-history.md))
and is under active development. `docs/design/` is the living design record —
why the tool is shaped the way it is, and what's still unbuilt — not a
proposal awaiting approval. Docs-only changes update that record; changes
under the toolkit's own code follow normal build/lint/test discipline.

## How the design record is organized

The core design documents build on each other in this order:

1. **[job-stories.md](docs/design/job-stories.md)** — the motivating scenarios (JTBD format), written first.
2. **[Reference/llm-wiki.md](docs/design/Reference/llm-wiki.md)** — vendored, do-not-edit source material (Karpathy's
   original LLM Wiki pattern, plus a vendored
   "core setup guide" for building one from scratch). Treat these as read-only references, not our own writing — they're
   kept for citation/grounding.
3. **[idea.md](docs/design/idea.md)** — the design rationale: problem, constraints, chosen solution (LLM-Wiki + GitHub
   webhooks + a hosted agent as receiver), and the still-open gaps. This is the main document — most substantive edits
   belong here or get linked from here.
4. **[toolkit-spec.md](docs/design/toolkit-spec.md)** — technical spec for the toolkit (source adapters incl.
   GitHub/Jira payload shapes, skills, CLI surface) that implements idea.md's solution. As-built by default, with
   unbuilt scope called out under explicit "Not yet built"
   headings (adapters, the superseded adapter-era skill design, batching CLI extensions). Extends the static
   Raw/Wiki/Schema model from llm-wiki.md with mutable-source handling (Jira comment threads, field edits) that the
   original pattern doesn't cover.

Documents covering what's actually been built, narrower than the full design above:

5. **[CONTEXT.md](docs/design/CONTEXT.md)** — domain glossary (source vs. snapshot source, processed vs. covered,
   confidence vs. provenance marker, etc.).
6. **[implementation-history.md](docs/design/implementation-history.md)** — narrative of how the tool actually got
   built across two closed Wayfinder maps; links to `docs/adr/` for the "why"
   behind each resolved decision.

Active, not-yet-resolved design work lives alongside these rather than inside them:

- **[cross-linker-spec.md](docs/design/cross-linker-spec.md)** — skill spec for automated cross-referencing, still open
  (issue #94); see [cross-linker-scale-research.md](docs/design/cross-linker-scale-research.md) for in-flight research
  feeding into it.

## Key design decisions already made (don't re-litigate without reason)

- **Write gate**: every wiki write goes through a PR, no direct commits — for both LLM-authored content and
  deterministic tooling output. One write path to audit.
- **Source-linkage timing**: correlation between an external source (ticket, chat) and a code change happens at
  PR/commit time, not ticket-creation time — a ticket doesn't know which files it touches until a PR exists.
- **Version-controlled vs. snapshot sources**: source code/PRs are cited by
  `{repo, path, commit_sha}` pointer, never copied into `Raw/`. Sources without their own version history (Jira, Slack,
  Confluence) get copied in as versioned snapshots, keyed on a **stable external ID** — if a source can't supply one,
  ingestion is refused rather than fuzzy-matched.
- **Review model**: no new approval process — doc updates ride along in the same PR as the code change they document.

## Open gaps (see idea.md "Gaps" section)

- Security boundary for the receiver ingesting untrusted external content (ticket bodies, PR descriptions) into a
  write-capable agent.
- Whether PR-review friction will suppress automated updates in practice.
- Whether the LLM wiki should live in the same repo as the code or a separate one.

When extending the tool, prefer resolving or explicitly narrowing these gaps over adding new speculative scope.

## Agent skills

### Development branches

When implementing a new feature, create a development branch in the repository. Once the feature is complete and tested,
create a pull request (PR) to merge the changes into the main branch.

### Issue tracker

Issues are tracked in GitHub Issues (`callowayproject/wiki-toolkit`), via the `gh` CLI. See
`docs/agents/issue-tracker.md`.

### Triage labels

Default five-role vocabulary, used as-is (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`,
`wontfix`). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context layout — `CONTEXT.md` + `docs/adr/` at the repo root (neither exists yet; created lazily). See
`docs/agents/domain.md`.
