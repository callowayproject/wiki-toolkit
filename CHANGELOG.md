# Changelog

## 0.22.0 (2026-08-10)

[Compare the full difference.](https://github.com/callowayproject/wiki-toolkit/compare/0.21.0...0.22.0)

### New

- Add typed-relationships lint check (resolves #109). [8419c74](https://github.com/callowayproject/wiki-toolkit/commit/8419c748e37f91bf1e585829d35e75cbff2d389e)

  lint_wiki() now validates each relationships: entry's type against the
  fixed 7-value enum and resolves target against the wiki's known pages
  by title or path, flagging (not blocking) unrecognized types and
  unresolved targets. Malformed relationships blocks/entries are
  reported as violations instead of crashing lint.

## 0.21.0 (2026-08-10)

[Compare the full difference.](https://github.com/callowayproject/wiki-toolkit/compare/0.20.0...0.21.0)

### New

- Add batching and cross-linking design doc to documentation. [58eac19](https://github.com/callowayproject/wiki-toolkit/commit/58eac197f2decbe801ebe7c17325a2476f524fdc)

- Add confidence rollup drift lint check (resolves #108). [41c2fb8](https://github.com/callowayproject/wiki-toolkit/commit/41c2fb8c4472ee4d9fb9e28b193cb3a74e0707ec)

  lint_wiki() recomputes a note's confidence: rollup from its inline
  markers (^[inferred], ^[ambiguous], unmarked = extracted), one unit
  per bullet or per paragraph on non-bulleted content, rounded to 2
  decimals round-half-up, and flags any mismatch — no tolerance band,
  same pattern as the existing source_count drift check. A confidence:
  value that isn't a mapping is flagged rather than crashing the lint
  run.

- Add spec-handoff summary for metadata schema map (issue #88). [b25c5e5](https://github.com/callowayproject/wiki-toolkit/commit/b25c5e509a508722fdf0355602f9733ba9b76c54)

  Consolidates the 5 resolved decisions (confidence marker naming,
  inline syntax, relationship-type enum, and both lint checks) into
  one pointer document so a future session can write the formal
  **spec:** issue without re-deriving context from the closed tickets.

- Add relationships: target-resolution lint check (resolves #92). [e500f81](https://github.com/callowayproject/wiki-toolkit/commit/e500f815bb8c9a52013eebb1541efdb0bbd7966c)

  lint verifies a relationships: entry's target resolves to an
  existing page, reusing the existing missing-cross-reference
  resolution rule for body wikilinks. Flags, doesn't reject — the
  write gate's PR review is the enforcement point.

- Add fixed relationship-type enum and relationships: block (resolves #91). [577310a](https://github.com/callowayproject/wiki-toolkit/commit/577310ab2bca80d2d887969acbd4559ee9fb0a00)

  type is a fixed 7-value enum (extends/implements/contradicts/
  derived_from/uses/replaces/related_to), not a per-wiki extensible
  taxonomy, so edges stay comparable across wikis.

- Add manifest write/resolve helpers, finish ADR-0006 unification. [aa13c83](https://github.com/callowayproject/wiki-toolkit/commit/aa13c83a351a797fdb061c7afb8eb38bf9e072cf)

  \_write_manifest and \_resolve_source_entry mirror \_read_manifest,
  replacing the hand-rolled write and entry-lookup-or-raise blocks
  duplicated across apply_source_scan, compute_source_delta, and
  write_source_snapshot.

### Other

- Pin down confidence: rollup counting/rounding/drift rule (resolves #93). [04ac8db](https://github.com/callowayproject/wiki-toolkit/commit/04ac8db961d55a0e91d26fb4c996d0dddf95bfde)

  Recompute-and-flag-drift confirmed, same pattern as source_count:
  counts bullets (or paragraphs on non-bulleted pages), 2 decimal
  places round-half-up, exact match after rounding with no tolerance
  band. lint's capability line updated to mention both the
  **relationships:** target check and confidence: drift check.

- Pin down confidence-marker + source-citation stacking syntax (resolves #90). [44630c4](https://github.com/callowayproject/wiki-toolkit/commit/44630c42fab3eb67701e4b15134e82ebc2a43979)

  Confidence markers and ^[source_id] citations stack as independent
  suffixes rather than combining into one bracket; confidence marker
  comes first: ^[inferred]^[design-doc-3].

### Updates

- Rename provenance marker to confidence marker (resolves #89). [f63a477](https://github.com/callowayproject/wiki-toolkit/commit/f63a4779fe8d033a685d147251faa5e75617df0d)

  Avoids collision with CONTEXT.md's existing "Provenance marker" term
  (.provenance skill-copy drift file). Renames the frontmatter rollup
  key provenance: to confidence: to match.

## 0.20.0 (2026-08-10)

[Compare the full difference.](https://github.com/callowayproject/wiki-toolkit/compare/0.19.0...0.20.0)

### New

- Add coordinator mechanism for serialized batch commits (#103). [ff270cf](https://github.com/callowayproject/wiki-toolkit/commit/ff270cf2cc38dbed14093cdcf3a2a6f9ba71f87c)

  Adds start-branch/commit-pages primitives so a batch coordinator can open
  one session branch, stream a real commit + log entry per source as each
  subagent's manifest lands, and close with the existing build/lint/propose-pr
  sequence reusing that branch — one PR per session regardless of batch count.
  Documents the coordinator's dispatch/staging/commit protocol in the ingest
  skill.

### Other

- Rewrite ingest skill sequence for session-level batching (#102). [c7d8ce3](https://github.com/callowayproject/wiki-toolkit/commit/c7d8ce3181ebfad4fcf21ee1ba60db71621c76aa)

  A session covering multiple manually-listed sources now runs source-scan,
  build, and lint once each and closes with a single propose-pr, instead of
  producing one PR per source. log stays per-source.

## 0.19.0 (2026-08-10)

[Compare the full difference.](https://github.com/callowayproject/wiki-toolkit/compare/0.18.2...0.19.0)

### Fixes

- Fix relative link to `CONTEXT.md` in `implementation-history.md` for consistency. [e767943](https://github.com/callowayproject/wiki-toolkit/commit/e767943c26ead3110cfe0a36ad86fbbde15126df)

### New

- Add batch-plan CLI subcommand (#101). [f73ad4d](https://github.com/callowayproject/wiki-toolkit/commit/f73ad4dd09942ea9b90ccd447edf1801d9be4b01)

  Splits files under a source directory into batches of at most 100,000
  bytes or 20 files, for parallel wiki-ingest subagent dispatch. Prints
  the plan as JSON per the documented schema.

### Other

- Research: prior art on cross-linking/link-suggestion at scale (#97). [60b6e80](https://github.com/callowayproject/wiki-toolkit/commit/60b6e80a67638ee8c7bace6041f83f348a140277)

### Updates

- Update `toolkit-spec.md` with v1 skills clarification, add `implementation-history.md`, and document core ADRs (`0001-0010`). [df19722](https://github.com/callowayproject/wiki-toolkit/commit/df19722e027cdc2fdb1ab243ec13839264cd9bf9)

## 0.18.2 (2026-08-09)

[Compare the full difference.](https://github.com/callowayproject/wiki-toolkit/compare/0.18.1...0.18.2)

### Other

- Warn in doctor on skills-copy version drift (#75). [90f9b4b](https://github.com/callowayproject/wiki-toolkit/commit/90f9b4b81ef2c65a544ebb88de4457227d991b5f)

  Extend `run_doctor` to compare docs/.agents/skills/.provenance against
  the installed wiki_toolkit version and surface drift as a blocking
  warning, consistent with how doctor already gates on shallow clones
  and malformed JSONL. Non-mutating: doctor never touches local files.

- Refine ingest skill documentation for clarity and precision. Streamlined instructions and adjusted formatting for consistency. [3f1bed4](https://github.com/callowayproject/wiki-toolkit/commit/3f1bed45081076a8946eddf6363a0d227583ebe8)

## 0.18.1 (2026-08-08)

[Compare the full difference.](https://github.com/callowayproject/wiki-toolkit/compare/0.18.0...0.18.1)

### New

- Add maintain skill. [b2ab34d](https://github.com/callowayproject/wiki-toolkit/commit/b2ab34df704351884a8914913d57334d048199a1)

  Orchestrates lint, source-update, and ingest per the periodic sweep
  described in issue #73, delegating instead of duplicating their logic.

- Add source-update skill. [3f4c78d](https://github.com/callowayproject/wiki-toolkit/commit/3f4c78d23c24a812cf83553cf4eab4d9eb42baba)

  Refreshes wiki pages for sources whose fields changed since the last
  Raw revision on main, using source-scan --update + source-delta.
  Closes #72.

- Add lint skill. [030ae33](https://github.com/callowayproject/wiki-toolkit/commit/030ae332d88f7963849330e33174c89823c962c9)

  Implements issue #71: skills/lint/SKILL.md runs the deterministic
  lint/source-lint/source-coverage trio, then a semantic pass for
  contradictions, staleness, orphan pages, and missing cross-references.
  Mechanical fixes (e.g. a missing wikilink) route through the write gate
  with --frame needs-review; contradictions and staleness are surfaced in
  the report only. Manually verified end-to-end against a scaffolded wiki
  with a seeded source_count violation and a seeded orphan page.

- Add plugin scaffold and ingest/query skills (#70). [5f13181](https://github.com/callowayproject/wiki-toolkit/commit/5f13181f715191d6f65dd6fc76f8229de8bf25ac)

  Adds the installable plugin skeleton (.claude-plugin/plugin.json,
  marketplace.json) plus skills/ingest and skills/query, whose command
  sequences were manually verified end-to-end against a scaffolded
  docs/ tree (source-scan -> write page -> build -> lint -> log ->
  propose-pr, and search-catalog -> cite -> optional write-back).

### Other

- Extend init to scaffold a local copy of the five skills (#74). [6de3a83](https://github.com/callowayproject/wiki-toolkit/commit/6de3a83a57b4846ad608e44abdf0c4ce12e9a108)

  run_init now copies each skills/<name>/SKILL.md into
  docs/.agents/skills/ and writes a .provenance file recording the
  installed wiki_toolkit version. Idempotent: reports an existing copy
  as already-present without touching it, matching the pattern used for
  every other scaffolded item.

  Packages skills/ into the wheel (wiki_toolkit/skills/) via hatch
  force-include, since the plugin's skills/ directory lives at the repo
  root but run_init needs it available post-install too.

- Extend command allowlist to include `git checkout`. [ba6ce8d](https://github.com/callowayproject/wiki-toolkit/commit/ba6ce8d7d9004d908f3637147cfb36de70ddd7c0)

## 0.18.0 (2026-08-08)

[Compare the full difference.](https://github.com/callowayproject/wiki-toolkit/compare/0.17.0...0.18.0)

### Updates

- Remove dead Delta.new_comment_ids field. [23eabc4](https://github.com/callowayproject/wiki-toolkit/commit/23eabc4ddef6a9d41e7fbaa930363efbb400c6d4)

  comments now materialize as new Raw sources via ingest, never
  source-update, so the field compute_source_delta never populated
  had no reader left.

  Fixes #69

## 0.17.0 (2026-08-07)

[Compare the full difference.](https://github.com/callowayproject/wiki-toolkit/compare/0.16.0...0.17.0)

### Updates

- Refactor type hints for flexibility and standardize CLI error handling with `click.UsageError`. [73c6ed5](https://github.com/callowayproject/wiki-toolkit/commit/73c6ed5254b921d22fc06235b50c38a8b63d4c16)

## 0.16.0 (2026-08-07)

[Compare the full difference.](https://github.com/callowayproject/wiki-toolkit/compare/0.15.1...0.16.0)

### New

- Add init command to scaffold docs/ structure. [33825ac](https://github.com/callowayproject/wiki-toolkit/commit/33825ac73cc41df0a7ae2018c4131aa5b4181f08)

  Creates sources/, wiki/, catalog.jsonl, log.jsonl, source-manifest.jsonl,
  and schema.md (verbatim from toolkit-spec.md). Refuses to overwrite
  existing items, reporting them as already-present so a partial init can
  be completed by re-running.

  Closes #57

## 0.15.1 (2026-08-07)

[Compare the full difference.](https://github.com/callowayproject/wiki-toolkit/compare/0.15.0...0.15.1)

### Other

- Retrofit --docs-dir onto the 10 remaining CLI commands. [c3bf1b3](https://github.com/callowayproject/wiki-toolkit/commit/c3bf1b3c4df3f0e21d9e843547fa0734f838891e)

  build, lint, source-scan, source-lint, source-coverage, source-dedupe,
  source-delta, source-snapshot, search-catalog, and log each hardcoded
  docs_dir = Path.cwd() / "docs"; now they resolve it through settings.py's
  flag > env > pyproject > default precedence, matching doctor/config show.

  propose-pr is deliberately excluded: it operates on git root, not docs_dir,
  so the flag wouldn't be meaningfully wired to anything.

  Closes #56

## 0.15.0 (2026-08-07)

[Compare the full difference.](https://github.com/callowayproject/wiki-toolkit/compare/0.14.0...0.15.0)

### New

- Add settings resolution module, config show, and doctor provenance line. [d71c432](https://github.com/callowayproject/wiki-toolkit/commit/d71c432c20f8704b5cdd11e59ba843e978b8bbdb)

  Resolves docs_dir via CLI flag > WIKI_TOOLKIT_DOCS_DIR env > nearest
  pyproject.toml [tool.wiki_toolkit] table > default, using
  pydantic-settings for both the env and pyproject legs. Wires the
  resolver into a new `config show` command and into `doctor`, whose
  run_doctor now takes docs_dir directly instead of deriving it from
  root.

  Closes #55

### Other

- "Refactor and reorganize documentation, templates, and tooling". [bcf0e5f](https://github.com/callowayproject/wiki-toolkit/commit/bcf0e5ff6a6bfa28b930812cdde605be4bacff28)

  - Removed redundant development-related documentation (`development.md`); integrated relevant content into `CODING_STANDARDS.md`.
  - Created detailed Jinja2 templates for docstrings, including `parameters`, `raises`, `returns`, and `attributes` sections, supporting multiple styles (table, list, spacy).
  - Updated CSS with specific styles for new templates (`doc-label-dataclass`).
  - Refactored structure under `docs/`, merging and expanding tutorials with detailed step-by-step workflows.
  - Added a new `README.md` with installation and usage instructions.

### Updates

- Remove outdated reference to `Developer Guide` in documentation. [981ee42](https://github.com/callowayproject/wiki-toolkit/commit/981ee422fa99b4041f69c8aee1306dcfb95eda45)

## 0.14.0 (2026-08-06)

[Compare the full difference.](https://github.com/callowayproject/wiki-toolkit/compare/0.13.1...0.14.0)

### New

- Add frontmatter parsing module and tests; remove unused dependency. [2394283](https://github.com/callowayproject/wiki-toolkit/commit/23942831d6bb102f7e0dc06d176a5ba83be5eb00)

  Introduce `frontmatter.py` for parsing and dumping YAML frontmatter, providing a `Post` class for convenient metadata handling. Add comprehensive tests for parsing, dumping, and `Post` functionality. Drop unused `python-frontmatter` dependency, aligning with new custom implementation.

## 0.13.1 (2026-08-05)

[Compare the full difference.](https://github.com/callowayproject/wiki-toolkit/compare/0.13.0...0.13.1)

### Other

- Extract shared LoadError-violation helper; source-dedupe reports violations. [d041a0e](https://github.com/callowayproject/wiki-toolkit/commit/d041a0eff63c2322bb617a1b57dfe2b32035a6d3)

  The same 4-line \_iter_markdown/LoadError pattern was duplicated across
  lint_sources, scan_sources, source_coverage, and suggest_dedupe. Extract
  \_load_or_record_violation to a single helper.

  source-dedupe also never read suggest_dedupe's violations, silently
  ignoring malformed-frontmatter files with no message and a zero exit
  code. Print them and exit nonzero, matching source-scan/source-lint.

  Fixes #48

## 0.13.0 (2026-08-05)

[Compare the full difference.](https://github.com/callowayproject/wiki-toolkit/compare/0.12.5...0.13.0)

### Updates

- Delete core.py: business logic fully migrated to dedicated modules. [ab1d972](https://github.com/callowayproject/wiki-toolkit/commit/ab1d97232cc4aa5ed41a4837680fd980259d176c)

  core.py was already an empty stub with nothing importing from it, and
  test_core.py was a stale duplicate of test_io.py left over from the
  \_io.py extraction. __init__.py has never re-exported anything (only
  __version__), so there's no public surface to preserve there.

  Closes #44

## 0.12.5 (2026-08-05)

[Compare the full difference.](https://github.com/callowayproject/wiki-toolkit/compare/0.12.4...0.12.5)

### New

- Add CLI-level test for build's malformed-frontmatter handling. [6d1b6cc](https://github.com/callowayproject/wiki-toolkit/commit/6d1b6ccff26b1072f5716946d145fbda20f06dc9)

  Covers the new violation-surfacing behavior end-to-end through
  CliRunner, not just at the wiki.py unit level.

### Other

- Extract wiki_toolkit/wiki.py: catalog, lint, and search. [d9b258e](https://github.com/callowayproject/wiki-toolkit/commit/d9b258ee62082f01e4c787242dd98ac74f178a02)

  Moves build_catalog, lint_wiki, parse_tag_taxonomy, and search_catalog
  out of core.py into a new wiki.py module. Both build_catalog and
  lint_wiki now route through sources.py's shared \_iter_markdown walk
  helper, fixing build_catalog's malformed-frontmatter crash (previously
  only lint_wiki handled that case) and removing lint_wiki's own
  duplicate walk/try-except.

  build_catalog now returns a CatalogResult(entries, violations) instead
  of a bare list so malformed frontmatter is reported rather than
  raised; cli.py's build command unpacks .entries, its only change
  beyond imports.

  Closes #43

## 0.12.4 (2026-08-05)

[Compare the full difference.](https://github.com/callowayproject/wiki-toolkit/compare/0.12.3...0.12.4)

### Other

- Move suggest_dedupe, delta, and snapshot functions into sources.py. [6bb2ad1](https://github.com/callowayproject/wiki-toolkit/commit/6bb2ad129ae698593b7bdf025dd30f1a0453fc8b)

  Relocates suggest_dedupe, diff_content_fields, compute_source_delta,
  last_known_revision, and write_source_snapshot from core.py onto
  sources.py's shared \_iter_markdown walk helper. suggest_dedupe now
  reports malformed frontmatter as a violation instead of crashing.

  Closes #42

## 0.12.3 (2026-08-05)

[Compare the full difference.](https://github.com/callowayproject/wiki-toolkit/compare/0.12.2...0.12.3)

### Other

- Move lint_sources/source_coverage into sources.py onto shared walk helper. [88ca812](https://github.com/callowayproject/wiki-toolkit/commit/88ca8123757fd18132313b8aa6125b723886378c)

  Rewrites both to call \_iter_markdown/\_is_canonical_source instead of
  duplicating the directory-walk and canonical-source logic (#40), which
  also fixes source_coverage's malformed-frontmatter crash. Relocates
  their tests to test_sources.py and adds a malformed-frontmatter case
  for source_coverage.

  Closes #41

### Updates

- Update settings.local.json: add support for "Bash(xargs cat)". [976a114](https://github.com/callowayproject/wiki-toolkit/commit/976a11408f0d597891cd6c342e92073ba9e71ec9)

## 0.12.2 (2026-08-05)

[Compare the full difference.](https://github.com/callowayproject/wiki-toolkit/compare/0.12.1...0.12.2)

### Other

- Extract sources.py: shared markdown walk helper + canonical-source predicate. [056bdd2](https://github.com/callowayproject/wiki-toolkit/commit/056bdd2d2bc5242275c4cb97012b605b3bed83fb)

  Moves scan_sources, apply_source_scan, and manifest read/write out of
  core.py into a new sources.py, routed through a shared \_iter_markdown
  walk helper and \_is_canonical_source predicate. Malformed frontmatter
  in scan_sources is now reported as a violation instead of raising.

- Extract log.py, write_gate.py, and doctor.py from core.py. [a2da52d](https://github.com/callowayproject/wiki-toolkit/commit/a2da52dace6c1b6807ad42236e2770a334dd022e)

  Splits three mutually-independent domain modules out of core.py:
  log.py (log.jsonl entries), write_gate.py (propose_pr, named after
  the write-gate decision in idea.md), and doctor.py (health check).
  cli.py's imports now point at the new modules; core.py keeps
  SOURCE_MANIFEST_FILENAME since it's used by its other functions.

  Closes #39

### Updates

- Update CLAUDE.md: add guidelines for development branches. [cf2afd7](https://github.com/callowayproject/wiki-toolkit/commit/cf2afd745125fdd404c12775f6fdf6e0e4caede7)

  Clarifies the development process by recommending feature branch creation and PR-based merging into the main branch.

## 0.12.1 (2026-08-05)

[Compare the full difference.](https://github.com/callowayproject/wiki-toolkit/compare/0.12.0...0.12.1)

### New

- Add documentation: Python docstring standards and coding guidelines. [04181d7](https://github.com/callowayproject/wiki-toolkit/commit/04181d792a51f8715678f92c71181f9a096c16a1)

  Includes a detailed guide for Python docstrings (Google style) and project coding standards enforced via pre-commit hooks (`ruff`, `mypy`, `pydoclint`, etc.).

- Add doctor integration test against a real, populated fixture repo. [c04d927](https://github.com/callowayproject/wiki-toolkit/commit/c04d927a0552031af064fef1a5fd1c0ddb507b0c)

  Closes gap in issue #22's DoD sweep: the full command surface already
  had unit + CliRunner coverage and mypy/ruff/pre-commit were already
  clean, but no test exercised doctor end-to-end after source-scan and
  build against a real (non-shallow) git clone.

### Other

- Extract JSONL read/write into wiki_toolkit/\_io.py. [a1fdbd6](https://github.com/callowayproject/wiki-toolkit/commit/a1fdbd63f992695313abfa34da31a3c2fe069cf2)

  Moves write_jsonl/read_jsonl out of core.py into a small internal
  utility module so later module-split tickets can import from it
  instead of core.py. No behavior change; core.py re-exports both
  names for existing callers (cli.py, tests/test_core.py).

  Closes #38

## 0.12.0 (2026-08-05)

[Compare the full difference.](https://github.com/callowayproject/wiki-toolkit/compare/0.11.0...0.12.0)

### Fixes

- Fix propose-pr tests: set repo-local git identity, not per-command -c flags. [4410208](https://github.com/callowayproject/wiki-toolkit/commit/4410208c6da711f5375163dcebcaf1ea95240913)

  CI runners have no global git user.name/user.email. The propose-pr test
  fixture only passed identity as one-off -c flags on the initial commit,
  so the later commit made inside propose_pr() itself (which correctly
  doesn't hardcode a fake identity, since it should attribute to whoever
  runs the tool) had nothing to fall back on and failed with "Author
  identity unknown". Setting repo-local config after `git init` persists
  the identity for every commit in the fixture, matching how a real
  git-configured environment behaves.

### New

- Add propose-pr command: local branch + commit write gate. [3d30382](https://github.com/callowayproject/wiki-toolkit/commit/3d3038214ad9d4de3422f36d5ea7e93a1863b0fa)

  Implements issue #21: propose-pr --pages <list> --frame routine|needs-review
  stages a wiki change as a new local git branch and commit, never pushing or
  opening a real GitHub PR. Commits are scoped to exactly the listed pages
  (ignoring anything else already staged), and a failed staging attempt rolls
  back to the original branch, deleting the stray branch.

### Updates

- Remove unused dependencies: `beautifulsoup4`, `decorator`, `future`, `geocoder`, `markdown-customblocks`, `ratelim`, `responses`, `setuptools`, `soupsieve`, and `yamlns`. [20a25f7](https://github.com/callowayproject/wiki-toolkit/commit/20a25f7493dc9e4de7c2b9b410e7e61dacb32290)

- Update dependencies: bump `gitpython` to 3.1.58, `packaging` to 26.3, `pytest-cov` to 7.1.0; downgrade `markdown-customblocks` to 1.4.1, `urllib3` to 1.26.20; and remove `pillow` and `python-magic`. [03de695](https://github.com/callowayproject/wiki-toolkit/commit/03de695999633f79e14aef2a93dca65fa0f25381)

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
