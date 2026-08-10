# ADR-0005: Two-layer testing strategy, no golden files

- **Status:** Accepted
- **Date:** 2026-08-04
- **Source tickets:** [#7](https://github.com/callowayproject/wiki-toolkit/issues/7)

## Context

The thin-CLI architecture ([ADR-0002](0002-cli-framework-and-thin-cli-architecture.md)) and the git-backed delta mechanism ([ADR-0004](0004-git-history-as-revision-store.md)) both needed a settled testing approach before command implementation could start.

## Decision

- **Unit tests** on internal business-logic functions carry the real coverage: source classification, delta computation, frontmatter diffing, coverage computation, etc.
- **`CliRunner` adapter tests** (one per command) assert only argument parsing, correct delegation, exit code, and output — no re-verification of business logic already covered at the unit layer.
- **No golden-file byte-diff comparisons** against `catalog.jsonl`/`log.jsonl` — structured assertions on parsed JSONL instead, since field-order/whitespace churn would make golden files brittle for no benefit.
- **`source-delta`'s git mechanics are tested against a real throwaway repo** in `tmp_path` (init repo, commit "last known," mutate uncommitted as "current") — not mocked `git` calls — covering the normal, no-prior-commit, and shallow-clone cases.
- **Fixture strategy**: per-command isolated fixtures built from a shared factory helper (e.g. `make_source(tmp_path, source, status=...)`), not one shared "golden wiki" repo — keeps each test's setup minimal and prevents cross-test ripple effects.

## Consequences

- Definition of Done for every v1 command = one unit test + one `CliRunner` test, `mypy`/`ruff`/pre-commit clean, and `doctor` passing against a real fixture repo (settled and swept in [#22](https://github.com/callowayproject/wiki-toolkit/issues/22)).
