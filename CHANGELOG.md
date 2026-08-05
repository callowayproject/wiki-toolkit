# Changelog

## 0.11.0 (2026-08-05)

[Compare the full difference.](https://github.com/callowayproject/wiki-toolkit/compare/0.10.0...0.11.0)

### New

- Add source-dedupe command. [5dfa86a](https://github.com/callowayproject/wiki-toolkit/commit/5dfa86ae351cbd131e143e82077fc69ff3872c41)

  Rule-based (mtime + content-similarity) keep/discard suggestions for
  docs/sources/ files sharing a source id where at least one is flagged
  **duplicate:** true. Suggestion-only, mirroring the write-gate on

## 0.10.0 (2026-08-05)

[Compare the full difference.](https://github.com/callowayproject/wiki-toolkit/compare/0.9.0...0.10.0)

### New

- Address code-review finding: source-snapshot must produce a real record. [0df26b7](https://github.com/callowayproject/wiki-toolkit/commit/0df26b78178d888d672d6c1192a21827d4f76f99)

  Resetting `processed` alone left no evidence a snapshot happened. Now also
  stamps a fresh update_sha/updated pair into the manifest, reusing the
  "computed SHA of files for mutable sources" case update_sha's docstring
  already describes — giving source-snapshot an actual versioned record per
  the spec, not just a bookkeeping flag flip.

- Add source-snapshot command. [761f3f9](https://github.com/callowayproject/wiki-toolkit/commit/761f3f9530f4f941e8e97f03e78ca50027238c1f)

  Writes a new Raw snapshot unit for a source under --units comments|fields,
  resetting `processed` (the existing reprocessing signal) so the next
  source-scan/source-delta picks it up. Works entirely against pre-materialized
  content on disk; v1 has no live adapter fetch, so --units is a bookkeeping
  distinction for downstream framing, not a different write.

  Closes #19

## 0.9.0 (2026-08-05)

[Compare the full difference.](https://github.com/callowayproject/wiki-toolkit/compare/0.8.0...0.9.0)

### New

- Address code-review findings on source-delta. [aad5929](https://github.com/callowayproject/wiki-toolkit/commit/aad592955f9f05c63abdc5eac9d5901aeced74d8)

  Guard the git-show call in last_known_revision so a failure there also
  degrades to the synthetic-empty-baseline path, matching the "never errors"
  contract. Distinguish [NEW] fields from [CHANGED] fields in CLI output
  for first-time sources.

- Add source-delta command. [ad7d087](https://github.com/callowayproject/wiki-toolkit/commit/ad7d08778ac057d12e7c4c37d612910ce3fecdd9)

  Diffs a source's current working-tree content against its last-known
  revision on main via real git log/show, excluding processed/duplicate/source
  bookkeeping fields. Sources with no prior commit on main diff against a
  synthetic empty baseline instead of erroring.

  Closes #18

## 0.8.0 (2026-08-05)

[Compare the full difference.](https://github.com/callowayproject/wiki-toolkit/compare/0.7.0...0.8.0)

### New

- Add source-coverage command. [fe391bf](https://github.com/callowayproject/wiki-toolkit/commit/fe391bfd8d900c48921621447db372ab5006b8a3)

  Cross-references source-manifest.jsonl's covered_by field against
  catalog.jsonl's sources lists to report which docs/sources/ files are
  covered by at least one wiki note. Excludes duplicate-flagged sources,
  consistent with source-scan.

  Closes #17

### Other

- Align source-coverage's exclusion rule with source-scan. [ba272a3](https://github.com/callowayproject/wiki-toolkit/commit/ba272a3c6751a9af8694aeaf2cf61e66e9f7c10e)

  source-coverage only checked the on-disk duplicate flag, missing the
  in-pass case where a later file shares a source id not yet stamped.
  Also skip version_controlled sources, as scan_sources does.

  Found in code review of #17.

## 0.7.0 (2026-08-04)

[Compare the full difference.](https://github.com/callowayproject/wiki-toolkit/compare/0.6.0...0.7.0)

### New

- Add source-lint command to validate source frontmatter and coverage. [1756d19](https://github.com/callowayproject/wiki-toolkit/commit/1756d191306bcc7e7c7a098d64f04a64f0296cdc)

  Flags missing `source` field and invalid processed/duplicate values as
  hard errors; reports processed-but-not-covered_by sources as a backlog
  list, distinct from errors, per issue #16.

## 0.6.0 (2026-08-04)

[Compare the full difference.](https://github.com/callowayproject/wiki-toolkit/compare/0.5.0...0.6.0)

### New

- Address code review: LogEntry dataclass, auto-create docs/, output assertions. [c9998b1](https://github.com/callowayproject/wiki-toolkit/commit/c9998b18ab31510dec1594926d5f0b500a08d6e4)

  Matches the existing pattern (CatalogEntry, SourceScanEntry) instead of a
  bare dict; append_log_entry now creates docs/ if missing rather than
  crashing on a first-run log call.

- Add log command to append entries to docs/log.jsonl. [83b71b3](https://github.com/callowayproject/wiki-toolkit/commit/83b71b32706b9b08f40ec63a100066dd8bf23e30)

  Implements issue #15: build_log_entry/append_log_entry are pure functions
  independent of Click, validating action against the allowed set and
  appending without rewriting existing lines. The `log` CLI command delegates
  to them.

## 0.5.0 (2026-08-04)

[Compare the full difference.](https://github.com/callowayproject/wiki-toolkit/compare/0.4.0...0.5.0)

### New

- Add search-catalog command to search compiled wiki notes. [7e5d113](https://github.com/callowayproject/wiki-toolkit/commit/7e5d113ee61d9aa7dd50b4ab58a16c65c2051e1f)

  Internal search logic (search_catalog) is a pure function independent
  of Click; the search-catalog CLI command delegates and formats results.

  Closes #14

## 0.4.0 (2026-08-04)

[Compare the full difference.](https://github.com/callowayproject/wiki-toolkit/compare/0.3.0...0.4.0)

### New

- Add lint: validate wiki note frontmatter, tags, source links, source_count. [0bc00c6](https://github.com/callowayproject/wiki-toolkit/commit/0bc00c6006f006adaf31cb311a6b1f9c78454a01)

  Closes #13

### Other

- Declare pyyaml explicitly, document source_count in frontmatter template. [c35cd9b](https://github.com/callowayproject/wiki-toolkit/commit/c35cd9be97a17a210aa6d7ace3570782d7355ad6)

  Review follow-up: lint's yaml.YAMLError catch relied on python-frontmatter's
  transitive pyyaml dependency without declaring it; source_count had no
  documented home in the wiki note frontmatter template despite lint checking it.

## 0.3.0 (2026-08-04)

[Compare the full difference.](https://github.com/callowayproject/wiki-toolkit/compare/0.2.0...0.3.0)

### New

- Add build: generate catalog.jsonl from wiki notes. [b90af21](https://github.com/callowayproject/wiki-toolkit/commit/b90af21c647df6d924b426b58a1691bbd12f7ace)

  wiki-toolkit build walks docs/wiki/, parses each note's frontmatter into
  a CatalogEntry (path, title, updated, sources, status), and writes
  docs/catalog.jsonl. status is resolved iff every referenced source is
  resolved in the source manifest, else proposed.

  Closes #12

## 0.2.0 (2026-08-04)

[Compare the full difference.](https://github.com/callowayproject/wiki-toolkit/compare/0.1.0...0.2.0)

### New

- Add source-scan: classify docs/sources/ files, write manifest. [00c4f91](https://github.com/callowayproject/wiki-toolkit/commit/00c4f9102b0884f7f47a43b9b792037b455f3833)

  Walks docs/sources/, classifies each frontmatter-tagged file as
  new/update/duplicate against docs/source-manifest.jsonl (first-seen
  wins, later same-`source` files stay excluded once flagged
  **duplicate:** true), and skips version-controlled sources. --update

- Add `.claude/settings.local.json` to configure permissions for CLI commands. [2f862dd](https://github.com/callowayproject/wiki-toolkit/commit/2f862dd0172f0e6bc186a2e887d9a72536de6bf2)

- Add doctor command: docs/ health check with shallow-clone warning. [faeb16c](https://github.com/callowayproject/wiki-toolkit/commit/faeb16cea7f2a8682e951f1197f3a81224895b52)

  Implements #10: a non-mutating `wiki-toolkit doctor` that reports
  docs/ structure presence, note counts, malformed JSONL, and shallow
  git clones (which break source-delta's last-known-revision lookup).
  Logic lives in wiki_toolkit.core.run_doctor, independent of Click.

- Add `.claude/settings.local.json` to configure permissions for CLI commands. [82ee5db](https://github.com/callowayproject/wiki-toolkit/commit/82ee5db894610146813adf1a73e00bc3b5ee3148)

- Add foundational testing guides, documentation, and DevOps wiki structure. [3ab4a7c](https://github.com/callowayproject/wiki-toolkit/commit/3ab4a7c44847a2d172415469f2c8d4225ec3d8d7)

### Other

- Set `GH_TOKEN` environment variable in `bump-version.yaml` workflow. [d326198](https://github.com/callowayproject/wiki-toolkit/commit/d3261985e00c1b2a840d7b1e109c089405eadbad)

- Scaffold CLI skeleton, dependency swap, and shared test fixture (#9). [c492359](https://github.com/callowayproject/wiki-toolkit/commit/c492359602d534be0d347d77de2e1d34d8a22d61)

  Replaces the fastapi/opentelemetry/structlog stack with click +
  python-frontmatter, activates the wiki-toolkit entry point, and splits
  CLI parsing (cli.py) from business logic (core.py) per the toolkit
  spec's thin-adapter design. Adds a make_source pytest fixture so later
  command tickets can build minimal per-test source fixtures instead of
  a shared golden-wiki repo.

- Bump the github-actions group across 1 directory with 10 updates. [020fb23](https://github.com/callowayproject/wiki-toolkit/commit/020fb23674c5d4b28a29ed5d6c55ab178decbf9f)

  Bumps the github-actions group with 10 updates in the / directory:

  | Package | From | To |
  | --- | --- | --- |
  | [actions/checkout](https://github.com/actions/checkout) | `4` | `7` |
  | [actions/download-artifact](https://github.com/actions/download-artifact) | `4` | `8` |
  | [actions/setup-python](https://github.com/actions/setup-python) | `5` | `7` |
  | [astral-sh/setup-uv](https://github.com/astral-sh/setup-uv) | `5` | `7` |
  | [github/codeql-action](https://github.com/github/codeql-action) | `3` | `4.37.4` |
  | [docker/login-action](https://github.com/docker/login-action) | `3` | `4` |
  | [docker/metadata-action](https://github.com/docker/metadata-action) | `5` | `6` |
  | [docker/build-push-action](https://github.com/docker/build-push-action) | `6` | `7` |
  | [actions/attest-build-provenance](https://github.com/actions/attest-build-provenance) | `2` | `4` |
  | [softprops/action-gh-release](https://github.com/softprops/action-gh-release) | `2` | `3` |

  Updates `actions/checkout` from 4 to 7

  - [Release notes](https://github.com/actions/checkout/releases)
  - [Changelog](https://github.com/actions/checkout/blob/main/CHANGELOG.md)
  - [Commits](https://github.com/actions/checkout/compare/v4...v7)

  Updates `actions/download-artifact` from 4 to 8

  - [Release notes](https://github.com/actions/download-artifact/releases)
  - [Commits](https://github.com/actions/download-artifact/compare/v4...v8)

  Updates `actions/setup-python` from 5 to 7

  - [Release notes](https://github.com/actions/setup-python/releases)
  - [Commits](https://github.com/actions/setup-python/compare/v5...v7)

  Updates `astral-sh/setup-uv` from 5 to 7

  - [Release notes](https://github.com/astral-sh/setup-uv/releases)
  - [Commits](https://github.com/astral-sh/setup-uv/compare/v5...v7)

  Updates `github/codeql-action` from 3 to 4.37.4

  - [Release notes](https://github.com/github/codeql-action/releases)
  - [Changelog](https://github.com/github/codeql-action/blob/main/CHANGELOG.md)
  - [Commits](https://github.com/github/codeql-action/compare/v3...v4.37.4)

  Updates `docker/login-action` from 3 to 4

  - [Release notes](https://github.com/docker/login-action/releases)
  - [Commits](https://github.com/docker/login-action/compare/v3...v4)

  Updates `docker/metadata-action` from 5 to 6

  - [Release notes](https://github.com/docker/metadata-action/releases)
  - [Commits](https://github.com/docker/metadata-action/compare/v5...v6)

  Updates `docker/build-push-action` from 6 to 7

  - [Release notes](https://github.com/docker/build-push-action/releases)
  - [Commits](https://github.com/docker/build-push-action/compare/v6...v7)

  Updates `actions/attest-build-provenance` from 2 to 4

  - [Release notes](https://github.com/actions/attest-build-provenance/releases)
  - [Changelog](https://github.com/actions/attest-build-provenance/blob/main/RELEASE.md)
  - [Commits](https://github.com/actions/attest-build-provenance/compare/v2...v4)

  Updates `softprops/action-gh-release` from 2 to 3

  - [Release notes](https://github.com/softprops/action-gh-release/releases)
  - [Changelog](https://github.com/softprops/action-gh-release/blob/master/CHANGELOG.md)
  - [Commits](https://github.com/softprops/action-gh-release/compare/v2...v3)

  ______________________________________________________________________

  **updated-dependencies:** - dependency-name: actions/attest-build-provenance
  dependency-version: '4'
  dependency-type: direct:production
  update-type: version-update:semver-major
  dependency-group: github-actions

  **signed-off-by:** dependabot[bot] <support@github.com>

### Updates

- Update references, fix emoji configuration, and add CONTEXT glossary. [6da2635](https://github.com/callowayproject/wiki-toolkit/commit/6da2635d888c7fd2edc7da80d04e29b128d06090)

- Update workflows to use `properdocs` for documentation deployment. [b0590cc](https://github.com/callowayproject/wiki-toolkit/commit/b0590ccee049cc5ac09cf61a0be9b8893ea19ed1)

- Update CHANGELOG with unreleased changes and new release notes. [5931095](https://github.com/callowayproject/wiki-toolkit/commit/593109526c2360169dceb1b139f0e850a8614af8)

- Update dependencies, configurations, and documentation to fix trailing newline issues and bump pre-commit hooks. [f8ee241](https://github.com/callowayproject/wiki-toolkit/commit/f8ee241b4ac3723f3df1106cd1899e0ef940a895)

## 0.1.0 (2026-08-04)

### Other

- Initial commit. [9c1a531](https://github.com/callowayproject/wiki-toolkit/commit/9c1a531e54667d3446760a5547ac4826af3f6ccb)
