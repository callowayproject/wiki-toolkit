# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A design/pitch document set — not a codebase. There is no build, lint, or test
step; the "product" is the markdown documents themselves and the pitch they
build toward. Treat edits here as editing a proposal, not shipping code.

## The pitch this repo is building

The goal is to get org approval for **LLM-Wiki as an infra-documentation
standard**: piloted on one repo first, not mandated org-wide. The documents
build on each other in this order:

1. **[job-stories.md](docs/design/job-stories.md)** — the motivating scenarios (JTBD format), written first.
2. **[Reference/llm-wiki.md](docs/design/Reference/llm-wiki.md)** — vendored, do-not-edit
   source material (Karpathy's original LLM Wiki pattern, plus a vendored
   "core setup guide" for building one from scratch). Treat these as read-only
   references, not our own writing — they're kept for citation/grounding.
3. **[idea.md](docs/design/idea.md)** — the actual pitch: problem, constraints, chosen solution
   (LLM-Wiki + GitHub webhooks + a hosted agent as receiver), and the
   still-open gaps. This is the main document — most substantive edits belong
   here or get linked from here.
4. **[toolkit-spec.md](docs/design/toolkit-spec.md)** — technical spec for the toolkit (source adapters,
   skills, CLI surface) that would implement idea.md's solution. Extends the
   static Raw/Wiki/Schema model from llm-wiki.md with mutable-source handling
   (Jira comment threads, field edits) that the original pattern doesn't cover.

## Key design decisions already made (don't re-litigate without reason)

- **Write gate**: every wiki write goes through a PR, no direct commits — for
  both LLM-authored content and deterministic tooling output. One write path
  to audit.
- **Source-linkage timing**: correlation between an external source (ticket,
  chat) and a code change happens at PR/commit time, not ticket-creation time
  — a ticket doesn't know which files it touches until a PR exists.
- **Version-controlled vs. snapshot sources**: source code/PRs are cited by
  `{repo, path, commit_sha}` pointer, never copied into `Raw/`. Sources
  without their own version history (Jira, Slack, Confluence) get copied in
  as versioned snapshots, keyed on a **stable external ID** — if a source
  can't supply one, ingestion is refused rather than fuzzy-matched.
- **Review model**: no new approval process — doc updates ride along in the
  same PR as the code change they document.

## Open gaps (see idea.md "Gaps" section)

- Security boundary for the receiver ingesting untrusted external content
  (ticket bodies, PR descriptions) into a write-capable agent.
- Whether PR-review friction will suppress automated updates in practice.
- Whether the LLM wiki should live in the same repo as the code or a separate
  one.

When extending this pitch, prefer resolving or explicitly narrowing these
gaps over adding new speculative scope.

## Agent skills

### Development branches

When implementing a new feature, create a development branch in the repository. Once the feature is complete and tested, create a pull request (PR) to merge the changes into the main branch.

### Issue tracker

Issues are tracked in GitHub Issues (`callowayproject/wiki-toolkit`), via the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Default five-role vocabulary, used as-is (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context layout — `CONTEXT.md` + `docs/adr/` at the repo root (neither exists yet; created lazily). See `docs/agents/domain.md`.
