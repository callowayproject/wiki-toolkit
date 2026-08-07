---
title: Tutorials
summary: Tutorials for how to use Wiki Toolkit.
date: 2026-08-04T10:30:50.914606+00:00
---

# Your first wiki note

This tutorial walks you through the whole `wiki-toolkit` loop once, by hand: scaffolding a
`docs/` wiki, adding a source, writing a note that cites it, and staging the result as a PR.
By the end you'll have a clean `doctor` report and one entry in the catalog.

## Prerequisites

- Python 3.14+
- A git repository to work in
- `wiki-toolkit` installed:

```console
$ pip install wiki-toolkit
```

## 1. Scaffold the structure

`wiki-toolkit` doesn't create a wiki for you — there's no `init` command yet, so you build the
skeleton by hand. From the root of your git repo:

```console
$ mkdir -p docs/sources docs/wiki
$ touch docs/catalog.jsonl docs/log.jsonl docs/schema.md docs/source-manifest.jsonl
```

Check that it's recognized:

```console
$ wiki-toolkit doctor
Python: 3.14.0
Notes in docs/wiki/: 0
  [ok] docs/catalog.jsonl
  [ok] docs/log.jsonl
  [ok] docs/schema.md
  [ok] docs/source-manifest.jsonl
  [ok] docs/sources
  [ok] docs/wiki
```

No `[MISSING]` or `[MALFORMED]` lines means the structure is sound.

## 2. Add a source

Every wiki note has to cite at least one **source** — a Raw snapshot of something outside the
wiki (a ticket, a PR, a doc). Create `docs/sources/abc-1.md`:

```markdown
---
source: jira:ABC-1
processed: true
title: Add OAuth2 scopes to the ingest API
---
```

The `source:` value is a stable external ID — this is what wiki notes will reference. Run
`source-scan` to see it classified:

```console
$ wiki-toolkit source-scan --update
[NEW] docs/sources/abc-1.md (jira:ABC-1)
Wrote 1 entries to docs/source-manifest.jsonl
```

`--update` writes the classification into `docs/source-manifest.jsonl`, which is what `lint` and
`build` check wiki notes against.

## 3. Write a wiki note

Create `docs/wiki/oauth2-scopes.md`, citing the source from step 2:

```markdown
---
title: OAuth2 scopes for the ingest API
sources:
  - jira:ABC-1
source_count: 1
updated: 2026-08-06
---

The ingest API accepts an OAuth2 `ingest:write` scope, added to support the
new webhook receiver.
```

Lint it:

```console
$ wiki-toolkit lint
No lint violations found.
```

`lint` checks the note's frontmatter, that every listed source exists in the manifest, that
`source_count` matches the `sources` list, and (once you add one) that any `tags` are in
`docs/schema.md`'s tag taxonomy.

## 4. Build the catalog

```console
$ wiki-toolkit build
Wrote 1 entries to docs/catalog.jsonl
```

`docs/catalog.jsonl` now has one entry for `oauth2-scopes.md`. Its `status` is `proposed` —
`source-scan` always writes new manifest entries as `proposed`; a source only becomes
`resolved` once something (a reviewer, today — by hand) marks it so in
`docs/source-manifest.jsonl`. A note's `status` is `resolved` only once every source it cites is.

## 5. Search it

```console
$ wiki-toolkit search-catalog --query oauth2
OAuth2 scopes for the ingest API (docs/wiki/oauth2-scopes.md)
```

## 6. Stage it as a PR

`wiki-toolkit` never writes to your wiki directly — every mutation goes through this **write
gate**: a local git branch + commit that you then push and open for review yourself.

```console
$ wiki-toolkit propose-pr --pages docs/wiki/oauth2-scopes.md --pages docs/catalog.jsonl --frame routine
Created branch wiki-update/routine-20260806101500123456 (commit a1b2c3d4e5, frame=routine)
  [staged] docs/wiki/oauth2-scopes.md
  [staged] docs/catalog.jsonl
```

`--frame` tells reviewers how much scrutiny the change needs: `routine` for a straightforward
update, `needs-review` for anything you want a closer look at. `propose-pr` stops at the local
commit — it never pushes or opens a real PR for you.

## What's next

- The [How-to guides](../howtos/index.md) cover the mutable-source cases this tutorial skipped:
  deduping sources (`source-dedupe`), diffing a changed ticket (`source-delta`), and snapshotting
  a comment or field edit (`source-snapshot`).
- The [Reference](../reference/index.md) documents every command's flags and output in full.
- [Explanation](../explanation.md) covers *why* the write gate and source-linkage rules work this way.
