# ADR-0002: CLI framework and thin-CLI architecture

- **Status:** Accepted
- **Date:** 2026-08-04
- **Source tickets:** [#4](https://github.com/callowayproject/wiki-toolkit/issues/4),
    [#9](https://github.com/callowayproject/wiki-toolkit/issues/9)

## Context

The vendored `llm-breakdown.md` guide specifies `wiki_tool.py` using only the Python standard library
(argparse, manual YAML-ish parsing).
This repo's scaffolded `pyproject.toml` already carried `fastapi[standard]`, `opentelemetry-*`, `pydantic-settings`,
and `structlog` — none obviously relevant to a local CLI — plus a commented-out `[project.scripts]` entry point.

## Decision

- CLI framework: `click`.
    Frontmatter parsing: `python-frontmatter`.
- Kept from the scaffold: `orjson`, `pydantic-settings`.
- Stripped as template cruft: `fastapi[standard]`, all `opentelemetry-*` packages, `structlog`.
- `[project.scripts]` (`wiki-toolkit = wiki_toolkit.cli:cli`) activated.
- **Architecture constraint**: `cli.py` is a thin adapter — argument parsing, delegation, output formatting only.
    All business logic lives in internal library functions independent of Click, unit-tested directly.
    `cli.py` itself has no logic worth unit-testing beyond correct delegation.

## Consequences

- Every command ticket had to split "internal pure function" (real test coverage) from "`cli.py` wrapper"
    (`CliRunner` adapter test only) — see [ADR-0005](0005-two-layer-testing-strategy.md).
- This split is what later made the domain-module split ([ADR-0006](0006-domain-module-split.md)) a pure code-motion
    refactor: `cli.py`'s command surface never had to change, only its imports.
