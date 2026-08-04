# Changelog

## Unreleased (2026-08-04)

[Compare the full difference.](https://github.com/callowayproject/wiki-toolkit/compare/0.1.0...HEAD)

### New

- Add foundational testing guides, documentation, and DevOps wiki structure. [3ab4a7c](https://github.com/callowayproject/wiki-toolkit/commit/3ab4a7c44847a2d172415469f2c8d4225ec3d8d7)

### Other

- Scaffold CLI skeleton, dependency swap, and shared test fixture (#9). [c492359](https://github.com/callowayproject/wiki-toolkit/commit/c492359602d534be0d347d77de2e1d34d8a22d61)

  Replaces the fastapi/opentelemetry/structlog stack with click +
  python-frontmatter, activates the wiki-toolkit entry point, and splits
  CLI parsing (cli.py) from business logic (core.py) per the toolkit
  spec's thin-adapter design. Adds a make_source pytest fixture so later
  command tickets can build minimal per-test source fixtures instead of
  a shared golden-wiki repo.

### Updates

- Update dependencies, configurations, and documentation to fix trailing newline issues and bump pre-commit hooks. [f8ee241](https://github.com/callowayproject/wiki-toolkit/commit/f8ee241b4ac3723f3df1106cd1899e0ef940a895)

## 0.1.0 (2026-08-04)

### Other

- Initial commit. [9c1a531](https://github.com/callowayproject/wiki-toolkit/commit/9c1a531e54667d3446760a5547ac4826af3f6ccb)
