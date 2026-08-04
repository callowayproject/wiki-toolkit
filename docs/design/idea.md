# DevOps Wiki

## Pitch
- Audience: leadership / other teams. Decision requested: approve this as an org-wide infra-documentation standard.
- Concrete ask (near-term): approve a one-repo pilot, not an org-wide mandate. Repo selection is deferred until after approval.
- Success signal for the pilot: qualitative (a retro/survey with the piloting team on doc trust and onboarding friction), not a hard quantitative metric.

## Problem
-  Keeping documentation up-to-date and accurate in an infrastructure repository.
-  The infrastructure repository will primarily contain the code required to provision infrastructure using Terraform and Helm.
-  The documentation should provide someone a basic understanding of who, what, where, when, and why.

## Constraints
-  Multiple people with different skill levels are reviewing and updating the code
-  Sources or reasons for changes are typically external to the repository
-  Need to marry the source or reason (external) for the change with the actual change (internal)
-  People are lazy. If friction is forced in the change request, people will try to avoid it or work around it. If we need a source of a change, it should be easy to make.

## Possible sources for changes
- Issue tracker
    - GitHub Issues
    - Azure DevOps
    - Jira
    - Linear
- Wiki Page (Confluence)
- Chats via Slack or Teams
- Files stored somewhere
- External pull requests
    - Dependabot
    - Renovate

## Solution: one combined system
- [LLM-Wiki](llm-wiki.md) is the workflow: ingest/query/lint operations keep that bundle current as the repo changes.
- GitHub webhooks are the trigger: `pull_request: opened/synchronize`, not merge. That's what lets the doc diff land in the same PR the reviewer is already looking at, before it merges.
- A hosted agent harness (Agent) is the receiver: it updates the docs based on received GitHub events. Piloting this mainly requires wiring up webhooks to it, not building a new service.
- Review model: no new process. Agent pushes the doc update as a commit onto the same PR branch (not a separate PR); the same reviewer approves both diffs.
  - Bot-authored PRs: Renovate PRs get the same treatment. Agent and developers already have push access to Renovate branches (needed to test/adapt the updated modules), so nothing changes there. Dependabot PRs are out of scope for the pilot: GitHub blocks non-Dependabot pushes to `dependabot[bot]`-authored branches by default, and many orgs auto-merge them without human review, so there's no reviewer to approve a doc diff riding alongside.
- Source-linkage mechanism (resolves the "marrying" gap below): correlation happens at PR/commit time, not at ticket-creation time. A ticket doesn't say which files it touches until someone writes the PR. When a PR/commit references a ticket (trailer, description, branch name), the receiver fetches that source and feeds it, along with the diff, to the LLM agent, which writes the doc update and cites the source in `log.md`.
- External-trigger ingestion (design docs, Jira tickets, before any PR exists): a non-GitHub trigger (Jira webhook, or manual invocation for a Confluence design doc) lets Agent ingest the source immediately and write a *speculative* wiki page (`status: proposed` on both the source-manifest entry and the page frontmatter), synthesizing what infrastructure the source implies, ahead of any code change. This still goes through the same write gate as any other wiki write: Agent opens a docs-only PR, no direct commits, no exception for speculative content. When a later PR references the same source (same stable ID), the normal source-linkage mechanism above resolves it: Agent flips `status` to `resolved` on the manifest entry and the page as part of that PR's doc update.
- Retiring docs for removed infrastructure: no separate mechanism needed. Whole-file/module removal is determined by the source-manifest's existing `referenced_by` list (look up the removed path and archive the wiki pages that reference it); partial removal within a file that still exists is handled by the normal ingest-on-PR flow, which reads that file's diff.

## Gaps (still open)
- None

## Structure
- [toolkit-spec.md](toolkit-spec.md): specification for the AI skills and helper tools (Agent operates these) that implement the llm-wiki pattern, including how mutable sources (Jira comment chains, changing source code) are detected, versioned, and folded into the wiki.

References:
- https://github.com/AlmanacCode/codealmanac/
- https://github.com/NousResearch/hermes-agent/blob/main/skills/research/llm-wiki/SKILL.md
- https://github.com/lucasastorian/llmwiki/tree/master
- https://github.com/Astro-Han/karpathy-llm-wiki
- https://github.com/Ar9av/obsidian-wiki
