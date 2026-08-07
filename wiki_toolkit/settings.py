"""Resolves wiki_toolkit configuration (currently just `docs_dir`).

Precedence: CLI flag > `WIKI_TOOLKIT_DOCS_DIR` env var > nearest `pyproject.toml`'s
`[tool.wiki_toolkit]` table (found by walking upward from cwd, same convention as
ruff/mypy) > built-in default (`docs/` relative to cwd).
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict
from pydantic_settings.sources import PyprojectTomlConfigSettingsSource

ConfigSource = Literal["flag", "env", "pyproject", "default"]


class _EnvSettings(BaseSettings):
    """Reads `docs_dir` from the `WIKI_TOOLKIT_DOCS_DIR` environment variable."""

    model_config = SettingsConfigDict(env_prefix="WIKI_TOOLKIT_")

    docs_dir: Path | None = None


class _PyprojectSettings(BaseSettings):
    """Reads `docs_dir` from a `pyproject.toml`'s `[tool.wiki_toolkit]` table."""

    model_config = SettingsConfigDict(pyproject_toml_table_header=("tool", "wiki_toolkit"))

    docs_dir: Path | None = None

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Restrict this settings class to init kwargs and `pyproject.toml`, no env/dotenv/secrets."""
        return (init_settings, PyprojectTomlConfigSettingsSource(settings_cls))


@dataclass
class ResolvedConfig:
    """The resolved `docs_dir` and which source produced it."""

    docs_dir: Path
    source: ConfigSource


def _find_pyproject_docs_dir(start: Path) -> Path | None:
    """Walk upward from `start` for the nearest pyproject.toml's `[tool.wiki_toolkit].docs_dir`.

    Once a pyproject.toml is found, it is authoritative (matches ruff/mypy
    convention) — a missing table, missing key, or unparseable file there
    means "no pyproject source", not "keep looking further up".
    """
    for directory in (start, *start.parents):
        pyproject = directory / "pyproject.toml"
        if not pyproject.is_file():
            continue
        try:
            data = PyprojectTomlConfigSettingsSource(_PyprojectSettings, toml_file=pyproject)()
            docs_dir = _PyprojectSettings.model_validate(data).docs_dir
        except ValueError:
            # ponytail: both tomllib.TOMLDecodeError and pydantic's ValidationError subclass ValueError
            return None
        if docs_dir is None:
            return None
        return docs_dir if docs_dir.is_absolute() else directory / docs_dir
    return None


def resolve_docs_dir(flag: Path | None = None, cwd: Path | None = None) -> ResolvedConfig:
    """Resolve `docs_dir` per precedence: flag > env > pyproject > default."""
    if flag is not None:
        return ResolvedConfig(docs_dir=flag, source="flag")

    cwd = cwd or Path.cwd()

    env_docs_dir = _EnvSettings().docs_dir
    if env_docs_dir is not None:
        return ResolvedConfig(docs_dir=env_docs_dir, source="env")

    pyproject_docs_dir = _find_pyproject_docs_dir(cwd)
    if pyproject_docs_dir is not None:
        return ResolvedConfig(docs_dir=pyproject_docs_dir, source="pyproject")

    return ResolvedConfig(docs_dir=cwd / "docs", source="default")
