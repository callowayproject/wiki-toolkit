# Coding Standards

## Installing from source for development

`uv` is recommended. [Install `uv`](https://docs.astral.sh/uv/getting-started/installation/).


Clone the repo:

```shell
$ git clone https://github.com/callowayproject/wiki-toolkit
```

Setup the environment.

```shell
$ cd wiki-toolkit
$ uv sync --upgrade --all-groups
```

Run Wiki Toolkit's tests from the source tree on your machine:

```shell
$ uv run pytest
```

## Development Flow

This project uses the [GitHubFlow](https://docs.github.com/en/get-started/quickstart/github-flow) workflow.

Rationale:

* The primary branch is always releasable.
* Lightweight.
* Single long-lived branch. Less maintenance overhead, faster iterations.
* Simple for one person projects, as well as collaboration.

Put simply:

1. Anything in the primary branch is deployable
2. To work on something new, create a descriptively named branch off the primary branch (ie: new-oauth2-scopes)
3. Commit to that branch locally and regularly push your work to the same named branch on GitHub
4. When you need feedback or help, or you think the branch is ready for merging, open a pull request
5. After someone else has reviewed and signed off on the feature, you can merge it into the primary branch
6. Once it is merged and pushed to the primary branch, you can and should deploy immediately

## Merging

Merges are done via Pull Requests.


## Tags

Tags are used to denote releases.


## Code quality

Enforced by pre-commit (`.pre-commit-config.yaml`). Run `pre-commit run --all-files` before opening a PR.

## Ruff

- Formatter + linter, line length 119.
- Lint rule set (see `pyproject.toml` `[tool.ruff.lint]`): flake8-builtins, flake8-annotations, bugbear, blind-except, comprehensions, McCabe complexity, pydocstyle, pycodestyle, pyflakes, isort, PEP8 naming, NumPy/Pandas/Perflint checks, pygrep-hooks, Pylint conventions/errors/warnings, flake8-quotes, Ruff-specific rules, flake8-bandit, flake8-simplify, flake8-type-checking.
- `tests/*` has relaxed per-file ignores (missing type hints/annotations on test functions, branch/argument/statement complexity limits, blanket `# type: ignore`).

## mypy

- Runs with `--no-strict-optional --ignore-missing-imports`. No stricter project-level config — don't add speculative type-checking rigor beyond what these flags require.

## pydoclint

- Google-style docstrings, config in `pyproject.toml` `[tool.pydoclint]`.
- Does not require a `Returns:` section when nothing is returned, does not require type hints inside docstrings, does not check return types, skips `Raises:` checking.
- Excludes `tests/`.
- Format and section rules: see the [python-docstrings skill](.claude/skills/python-docstrings/SKILL.md).

## interrogate

- Docstring coverage gate, `fail-under = 90`.
- `__init__` methods and magic methods are exempt; nested functions/classes are exempt.
- Everything else (modules, classes, public/private/semi-private functions, setters) must have a docstring.

## Tests

Use the [python-tester skill](.claude/skills/python-tester/SKILL.md) for pytest patterns (AAA structure, fixtures, parametrization, mocking, coverage-by-meaning not by-percentage).
