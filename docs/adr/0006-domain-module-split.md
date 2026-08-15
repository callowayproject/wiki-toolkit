# ADR-0006: Domain-module split of core.py

- **Status:** Accepted
- **Date:** 2026-08-05
- **Source tickets:** [#37](https://github.com/callowayproject/wiki-toolkit/issues/37) (and children
    [#38](https://github.com/callowayproject/wiki-toolkit/issues/38)–[#44](https://github.com/callowayproject/wiki-toolkit/issues/44),
    [#48](https://github.com/callowayproject/wiki-toolkit/issues/48))

## Context

`wiki_toolkit/core.py` grew to 810 lines mixing six unrelated domain concepts
(source lifecycle, wiki catalog, the write gate, the audit log, doctor).
The same "walk a directory of frontmatter files" pattern was reimplemented six times
(`scan_sources`, `build_catalog`, `lint_wiki`, `lint_sources`, `source_coverage`, `suggest_dedupe`);
four of those six crashed on malformed frontmatter instead of reporting a lint violation,
and only one had test coverage for that failure mode.
The "a source file is canonical" rule
(first-seen `source` id, excluding `duplicate: true`)
was copy-pasted verbatim between `scan_sources` and `source_coverage`.

## Decision

- Split `core.py` into modules named after `CONTEXT.md`'s domain vocabulary: `sources.py`
    (the largest — owns the one domain concept, `source`, and all its state transitions),
    `wiki.py`, `write_gate.py`, `log.py`, `doctor.py`, plus a shared internal `_io.py` (JSONL read/write).
- One shared private directory-walk helper (`_iter_markdown`)
    and one shared canonical-source predicate (`_is_canonical_source`) replace all six/two duplicated implementations.
- `cli.py`'s command surface (names, options, output strings, exit codes) is completely unchanged —
    only its imports move.
- Malformed-frontmatter handling becomes uniform across all six former call sites
    as a side effect of the walk unification — a bug fix bundled into the refactor, not new scope.
- Tests move with the code they cover, split along the same module boundaries
    (`test_sources.py`, `test_wiki.py`, `test_write_gate.py`, `test_log.py`, `test_doctor.py`, `test_io.py`).

## Consequences

- Splitting `sources.py` further by individual command (`source_scan.py`/`source_coverage.py`/…) was explicitly
    rejected — it would recreate the original duplication one level up, since all of these share the manifest and the
    canonical-source rule.
- `core.py` is deleted once every symbol has a new home; nothing imports from `wiki_toolkit.core` afterward.
