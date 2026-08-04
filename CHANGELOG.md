# Changelog

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
