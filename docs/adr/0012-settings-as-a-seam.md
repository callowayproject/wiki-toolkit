# ADR-0012: Settings as a seam (Context, build_context, dedicated config file)

- **Status:** Accepted
- **Date:** 2026-08-16
- **Source tickets:** [#154](https://github.com/callowayproject/wiki-toolkit/issues/154) (and
    [#157](https://github.com/callowayproject/wiki-toolkit/issues/157)-[#160](https://github.com/callowayproject/wiki-toolkit/issues/160))
- **Supersedes:** the `docs_dir`-only precedence chain, `config show`,
    and `doctor` contracts from [ADR-0007](0007-settings-resolution-and-init.md).
    ADR-0007's `init` decision stands unchanged.

## Context

ADR-0007 resolved a single setting, `docs_dir`, through a four-tier chain (flag, env, `pyproject.toml`, default).
Three more settings needed the same treatment: `repo_root`
(already computed ad hoc in several commands),
and `branch_prefix`/`batch_byte_cap`/`batch_file_cap`
(previously hardcoded constants in `write_gate.py` and the batching module).
A non-Python host repo also had no config file that didn't compete for space in a `pyproject.toml` table meant
for Python tooling.

## Decision

- `wiki_toolkit/settings.py` gains a `Context` model (`docs_dir`, `repo_root`, `branch_prefix`,
    `batch_byte_cap`, `batch_file_cap`) and a `build_context()` entry point that resolves all five fields at
    once, in precedence order: CLI flag (only `docs_dir`/`repo_root` have one) > `WIKI_TOOLKIT_<UPPER_SNAKE>`
    env var > `.wiki-toolkit.toml` dedicated file, found by walking upward from cwd > `[tool.wiki_toolkit]`
    table in the nearest `pyproject.toml` > built-in default.
- The dedicated file wins over the `pyproject.toml` table even when both are present, so a non-Python host
    repo has a config file that never has to compete with one meant for Python tooling. `doctor` warns when
    both exist, since only the dedicated file's values take effect.
- Resolution never raises.
    A malformed dedicated file, a malformed `pyproject.toml` table, or an individually invalid field value
    (empty `branch_prefix`, non-positive batch cap)
    is dropped and that field falls through to the next tier, rather than failing the whole field or the command.
- `build_context()` returns the `Context` alongside a per-field source map
    (`flag`/`env`/`dedicated_file`/`pyproject`/`default`).
    The CLI group callback calls it once per invocation and assigns the result to `ctx.obj`;
    every subcommand reads settings off that shared object via `@click.pass_obj` instead of re-declaring `--docs-dir`
    and re-resolving it per command.
- `config show` prints every field's resolved value and source, replacing the single-field `docs_dir`-only
    output.
- `doctor` prints the resolved configuration and source for every field (not just `docs_dir`), plus three new
    non-fatal warnings, never exit-1 failures: both a dedicated file and a `pyproject.toml` table present,
    `repo_root` falling back to `cwd` because no `.git` was found, and any field that fell back to `default`
    because an upstream tier's value for it was invalid.

## Consequences

- `write_gate.py` and the batching module read `branch_prefix`/`batch_byte_cap`/`batch_file_cap` off `Context`
    instead of module-level constants; both remain internal defaults, now overridable.
- Every CLI subcommand's default-resolution line collapses to reading `ctx.obj`; only the group callback
    performs resolution.
- `resolve_docs_dir()` (ADR-0007's four-tier, `docs_dir`-only function) stays in `settings.py` unused by the CLI;
    nothing currently calls it outside tests.
    It is not removed by this decision, since removing it is out of scope for the settings-seam work.
