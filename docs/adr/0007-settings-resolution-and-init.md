# ADR-0007: Settings resolution, init, and config show

- **Status:** Accepted
- **Date:** 2026-08-07
- **Source tickets:** [#54](https://github.com/callowayproject/wiki-toolkit/issues/54) (and
    [#55](https://github.com/callowayproject/wiki-toolkit/issues/55)–[#57](https://github.com/callowayproject/wiki-toolkit/issues/57))

## Context

`v1-spec.md` already specified a `docs_dir` configuration precedence chain and an `init` command,
but no code implemented either: every command hardcoded `docs_dir = Path.cwd() / "docs"`,
so there was no way to point the toolkit at a non-default docs root,
and no bootstrap path for a brand-new wiki other than hand-creating the structure `doctor` would otherwise just report
as missing.

## Decision

- `wiki_toolkit/settings.py` resolves `docs_dir` in precedence order:
    CLI flag → `WIKI_TOOLKIT_DOCS_DIR` env var → `[tool.wiki_toolkit]` table in `pyproject.toml`
    (located upward from cwd, matching how `ruff`/`mypy` locate project config) → built-in default (`docs/`).
    Resolution returns the value _and_ which source produced it (`flag`/`env`/`pyproject`/`default`)
    as a small result type, not a bare path.
- New `config show` command prints the resolved value and its source, read-only.
- New `init` command scaffolds `docs/{sources,wiki}/`, empty `catalog.jsonl`/`log.jsonl`/`source-manifest.jsonl`,
    and `schema.md` from a built-in template verbatim (unchanged from toolkit-spec.md's Schema section).
    It refuses to overwrite anything already present,
    reporting each already-present item instead of erroring the whole run —
    so a partial `init` can be completed by re-running.
- `doctor` gains the "resolved configuration and its source" line already promised by `v1-spec.md`'s contract but not
    yet implemented.
- All 9 pre-existing commands (plus `doctor`) are retrofitted with a `--docs-dir` option,
    replacing their hardcoded default.

## Consequences

- No business-logic module's function signature changes — they already took `docs_dir: Path` as a plain parameter;
    only `cli.py`'s option wiring and each command's default-resolution line change.
- `init` later gained a sixth scaffolded item
    (the local skills copy) without reopening this ADR — see [ADR-0009](0009-local-skill-copy-versioned-sync.md).
