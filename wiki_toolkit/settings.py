"""Resolves wiki_toolkit configuration.

`resolve_docs_dir()` resolves just `docs_dir` (precedence: CLI flag >
`WIKI_TOOLKIT_DOCS_DIR` env var > nearest `pyproject.toml`'s `[tool.wiki_toolkit]`
table > built-in default).

`build_context()` resolves the full `Context` (docs_dir, repo_root, branch_prefix,
batch_byte_cap, batch_file_cap) through a five-tier precedence chain: CLI flag >
`WIKI_TOOLKIT_<UPPER_SNAKE>` env var > nearest `.wiki-toolkit.toml` (dedicated file,
flat top-level keys) > nearest `pyproject.toml`'s `[tool.wiki_toolkit]` table >
built-in default. Each file tier is found by walking upward from cwd, same
convention as ruff/mypy; once found, it's authoritative for that tier (a broken
file or an invalid field value there falls through to the next tier rather than
continuing to search further up).
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ValidationError, field_validator
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict
from pydantic_settings.sources import (
    EnvSettingsSource,
    PyprojectTomlConfigSettingsSource,
    TomlConfigSettingsSource,
)

ConfigSource = Literal["flag", "env", "pyproject", "default"]
ContextConfigSource = Literal["flag", "env", "dedicated_file", "pyproject", "default"]

DEDICATED_FILENAME = ".wiki-toolkit.toml"

_DEFAULT_BRANCH_PREFIX = "wiki-update/"
_DEFAULT_BATCH_BYTE_CAP = 100_000
_DEFAULT_BATCH_FILE_CAP = 20


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


class Context(BaseModel):
    """The full resolved wiki_toolkit configuration."""

    docs_dir: Path
    repo_root: Path
    branch_prefix: str
    batch_byte_cap: int
    batch_file_cap: int


_CONTEXT_FIELDS = ("docs_dir", "repo_root", "branch_prefix", "batch_byte_cap", "batch_file_cap")
_PATH_FIELDS = ("docs_dir", "repo_root")


class _ContextFieldsSettings(BaseSettings):
    """Base for the optional per-tier settings sources: any field may be absent."""

    docs_dir: Path | None = None
    repo_root: Path | None = None
    branch_prefix: str | None = None
    batch_byte_cap: int | None = None
    batch_file_cap: int | None = None

    @field_validator("branch_prefix")
    @classmethod
    def _branch_prefix_not_empty(cls, value: str | None) -> str | None:
        """Reject an empty (but present) `branch_prefix`."""
        if value is not None and not value:
            raise ValueError("branch_prefix must not be empty")
        return value

    @field_validator("batch_byte_cap", "batch_file_cap")
    @classmethod
    def _cap_positive(cls, value: int | None) -> int | None:
        """Reject a non-positive (but present) batch cap."""
        if value is not None and value <= 0:
            raise ValueError("must be positive")
        return value


class _ContextEnvSettings(_ContextFieldsSettings):
    """Field-shape for reading `WIKI_TOOLKIT_*` env vars; env is read separately via `EnvSettingsSource`."""

    model_config = SettingsConfigDict(env_prefix="WIKI_TOOLKIT_")

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Restrict validation (`model_validate`) to init kwargs only.

        Without this, `model_validate` re-triggers the default env source and
        silently re-merges the *original* (possibly invalid) environment on
        top of the already-filtered dict passed to it.
        """
        return (init_settings,)


class _ContextDedicatedFileSettings(_ContextFieldsSettings):
    """Reads context fields from a dedicated `.wiki-toolkit.toml` file's flat top-level keys."""

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Restrict this settings class to init kwargs, no env/dotenv/secrets/toml-file discovery."""
        return (init_settings,)


class _ContextPyprojectSettings(_ContextFieldsSettings):
    """Field-shape for reading a `pyproject.toml`'s `[tool.wiki_toolkit]` table, read separately."""

    model_config = SettingsConfigDict(pyproject_toml_table_header=("tool", "wiki_toolkit"))

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Restrict validation (`model_validate`) to init kwargs only.

        `pyproject.toml` is read separately via an explicit `toml_file` path (the
        directory found by `_find_upward`); the default `PyprojectTomlConfigSettingsSource`
        resolves relative to the actual process cwd and would re-merge whatever it
        finds there on top of the already-filtered dict passed to `model_validate`.
        """
        return (init_settings,)


def _find_upward(start: Path, filename: str) -> Path | None:
    """Walk upward from `start` for the nearest directory containing `filename`."""
    for directory in (start, *start.parents):
        if (directory / filename).is_file():
            return directory
    return None


def _validate_dropping_invalid(cls: type[_ContextFieldsSettings], data: dict[str, object]) -> _ContextFieldsSettings:
    """Validate `data` against `cls`, dropping only the individually-invalid fields.

    One bad field (e.g. a negative `batch_byte_cap`) must not discard its
    valid siblings (e.g. a well-formed `docs_dir`) from the same tier.
    """
    remaining = dict(data)
    while True:
        try:
            return cls.model_validate(remaining)
        except ValidationError as exc:
            bad_fields = {str(err["loc"][0]) for err in exc.errors() if err["loc"]}
            if not bad_fields & remaining.keys():
                # ponytail: safety net against an infinite loop if a future validator
                # raises without loc matching a known field; not reachable today
                return cls.model_construct()
            for field in bad_fields:
                remaining.pop(field, None)


def _env_context_fields() -> _ContextFieldsSettings:
    """Read context fields from `WIKI_TOOLKIT_*` env vars, dropping any individually-invalid value."""
    data = EnvSettingsSource(_ContextEnvSettings, env_prefix="WIKI_TOOLKIT_")()
    return _validate_dropping_invalid(_ContextEnvSettings, data)


def _dedicated_file_context_fields(directory: Path | None) -> _ContextFieldsSettings | None:
    """Read context fields from `directory`'s `.wiki-toolkit.toml`, or `None` if missing/unparseable."""
    if directory is None:
        return None
    toml_file = directory / DEDICATED_FILENAME
    try:
        data = TomlConfigSettingsSource(_ContextDedicatedFileSettings, toml_file=toml_file)()
    except ValueError:
        # ponytail: tomllib.TOMLDecodeError subclasses ValueError
        return None
    return _validate_dropping_invalid(_ContextDedicatedFileSettings, data)


def _pyproject_context_fields(directory: Path | None) -> _ContextFieldsSettings | None:
    """Read context fields from `directory`'s `pyproject.toml` table, or `None` if missing/unparseable."""
    if directory is None:
        return None
    toml_file = directory / "pyproject.toml"
    try:
        data = PyprojectTomlConfigSettingsSource(_ContextPyprojectSettings, toml_file=toml_file)()
    except ValueError:
        return None
    return _validate_dropping_invalid(_ContextPyprojectSettings, data)


def _find_repo_root(cwd: Path) -> Path:
    """Walk upward from `cwd` for the nearest `.git`; fall back to `cwd` itself."""
    for directory in (cwd, *cwd.parents):
        if (directory / ".git").exists():
            return directory
    return cwd


def _default_value(field: str, cwd: Path) -> Path | str | int:
    """Return the built-in default for `field`."""
    if field == "docs_dir":
        return cwd / "docs"
    if field == "repo_root":
        return _find_repo_root(cwd)
    if field == "branch_prefix":
        return _DEFAULT_BRANCH_PREFIX
    if field == "batch_byte_cap":
        return _DEFAULT_BATCH_BYTE_CAP
    return _DEFAULT_BATCH_FILE_CAP


_Tier = tuple[ContextConfigSource, "_ContextFieldsSettings | None", "Path | None"]


def _resolve_field(
    field: str, flag_value: Path | None, tiers: tuple[_Tier, ...], cwd: Path
) -> tuple[object, ContextConfigSource]:
    """Resolve a single field's value and source, falling through `tiers` in order to `default`."""
    if flag_value is not None:
        return flag_value, "flag"

    for source_name, settings, base_dir in tiers:
        if settings is None:
            continue
        value = getattr(settings, field)
        if value is None:
            continue
        if field in _PATH_FIELDS and base_dir is not None and not value.is_absolute():
            value = base_dir / value
        return value, source_name

    return _default_value(field, cwd), "default"


def build_context(
    docs_dir_flag: Path | None = None,
    repo_root_flag: Path | None = None,
    cwd: Path | None = None,
) -> tuple[Context, dict[str, ContextConfigSource]]:
    """Resolve the full `Context` per field, tracking which tier produced each value.

    Precedence per field: CLI flag > env var > dedicated file > pyproject.toml > default.
    """
    cwd = cwd or Path.cwd()
    flags = {"docs_dir": docs_dir_flag, "repo_root": repo_root_flag}

    dedicated_dir = _find_upward(cwd, DEDICATED_FILENAME)
    pyproject_dir = _find_upward(cwd, "pyproject.toml")
    tiers: tuple[_Tier, ...] = (
        ("env", _env_context_fields(), None),
        ("dedicated_file", _dedicated_file_context_fields(dedicated_dir), dedicated_dir),
        ("pyproject", _pyproject_context_fields(pyproject_dir), pyproject_dir),
    )

    values: dict[str, object] = {}
    sources: dict[str, ContextConfigSource] = {}
    for field in _CONTEXT_FIELDS:
        values[field], sources[field] = _resolve_field(field, flags.get(field), tiers, cwd)

    return Context.model_validate(values), sources
