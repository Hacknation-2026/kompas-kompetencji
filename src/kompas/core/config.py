"""Layered YAML configuration with typed validation.

Resolution order (later wins):

1. ``config/base.yaml``
2. ``config/environments/<env>.yaml``   (env = ``KOMPAS_ENV`` or ``app.environment``)
3. ``config/models/<section>/<profile>.yaml`` for sections declaring ``profile``
   (``llm``, ``embeddings``) – inline ``provider``/``params`` in the section override the profile
4. environment variables ``KOMPAS__SECTION__KEY=value`` (values parsed as YAML scalars)
5. explicit ``overrides`` passed to :func:`load_settings` (used by tests)

Relative paths are resolved against the project root (parent of ``config/``).
"""

from __future__ import annotations

import copy
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator

from kompas.core.exceptions import ConfigurationError

ENV_PREFIX = "KOMPAS__"
ENV_SELECTOR = "KOMPAS_ENV"
CONFIG_DIR_ENV = "KOMPAS_CONFIG_DIR"
PROFILED_SECTIONS = ("llm", "embeddings")
INSECURE_SECRETS = {"__override_me__", ""}


def project_root() -> Path:
    """Repository root (``src/kompas/core/config.py`` -> 3 levels up from ``src``)."""
    return Path(__file__).resolve().parents[3]


# --------------------------------------------------------------------------- models
class _Section(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ComponentConfig(_Section):
    """``provider`` + ``params`` description of a pluggable component."""

    provider: str
    params: dict[str, Any] = Field(default_factory=dict)


class ProfiledComponentConfig(ComponentConfig):
    """Component whose defaults come from ``config/models/<section>/<profile>.yaml``."""

    profile: str | None = None


class AppConfig(_Section):
    name: str = "Kompas Kompetencji"
    version: str = "0.1.0"
    environment: str = "dev"
    debug: bool = False
    office_name: str = "Ministerstwo Cyfryzacji"
    timezone: str = "Europe/Warsaw"


class ServerConfig(_Section):
    host: str = "127.0.0.1"
    port: int = 8000
    reload: bool = False
    workers: int = 1
    api_prefix: str = "/api/v1"
    cors_origins: list[str] = Field(default_factory=list)


class SecurityConfig(_Section):
    jwt_secret: SecretStr
    jwt_algorithm: str = "HS256"
    token_ttl_minutes: int = 480
    password_hash_iterations: int = 200_000
    seed_users_file: Path | None = None


class PathsConfig(_Section):
    data_dir: Path = Path("data")
    models_dir: Path = Path("models")
    competency_model_file: Path
    workflows_file: Path
    forms_file: Path
    prompts_file: Path
    scoring_file: Path


class SeedConfig(_Section):
    employees_file: Path | None = None
    evaluations_file: Path | None = None


class AssistantConfig(_Section):
    knowledge_base_dir: Path
    faq_file: Path | None = None
    index_file: Path | None = None
    chunk_size: int = 180
    chunk_overlap: int = 40
    top_k: int = 4
    min_relevance: float = Field(0.35, ge=0.0, le=1.0)
    max_context_chars: int = 6000
    guardrails: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_overlap(self) -> AssistantConfig:
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("assistant.chunk_overlap must be smaller than chunk_size")
        return self


class ScoringConfig(_Section):
    indicator_aggregation: ComponentConfig


class NotificationsConfig(ComponentConfig):
    reminder_lead_days: int = 7


class Settings(_Section):
    """Root, fully validated application configuration."""

    app: AppConfig = Field(default_factory=AppConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)
    security: SecurityConfig
    paths: PathsConfig
    repository: ComponentConfig
    seed: SeedConfig = Field(default_factory=SeedConfig)
    llm: ProfiledComponentConfig
    embeddings: ProfiledComponentConfig
    retriever: ComponentConfig
    assistant: AssistantConfig
    scoring: ScoringConfig
    documents: ComponentConfig
    archive: ComponentConfig
    notifications: NotificationsConfig
    hr_system: ComponentConfig

    @model_validator(mode="after")
    def _production_guards(self) -> Settings:
        if self.app.environment == "prod" and self.security.jwt_secret.get_secret_value() in INSECURE_SECRETS:
            raise ValueError(
                "security.jwt_secret must be overridden in production (KOMPAS__SECURITY__JWT_SECRET)"
            )
        return self


# --------------------------------------------------------------------------- loading helpers
def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge ``override`` into a copy of ``base`` (dicts merge, everything else replaces)."""
    result = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def read_yaml(path: Path) -> dict[str, Any]:
    """Read a YAML mapping (empty file -> ``{}``)."""
    if not path.is_file():
        raise ConfigurationError(f"Configuration file not found: {path}")
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ConfigurationError(f"Configuration file must contain a mapping: {path}")
    return data


def env_overrides(environ: dict[str, str] | os._Environ[str]) -> dict[str, Any]:
    """Translate ``KOMPAS__A__B=value`` variables into a nested dict."""
    result: dict[str, Any] = {}
    for key, raw in environ.items():
        if not key.startswith(ENV_PREFIX):
            continue
        parts = [p.lower() for p in key[len(ENV_PREFIX) :].split("__") if p]
        if not parts:
            continue
        node = result
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = yaml.safe_load(raw) if raw != "" else ""
    return result


def _apply_profiles(data: dict[str, Any], config_dir: Path) -> dict[str, Any]:
    for section in PROFILED_SECTIONS:
        block = data.get(section)
        if not isinstance(block, dict) or not block.get("profile"):
            continue
        profile = read_yaml(config_dir / "models" / section / f"{block['profile']}.yaml")
        inline = {k: v for k, v in block.items() if k != "profile"}
        # If the inline block switches provider, profile params must not leak in.
        if "provider" in inline and inline["provider"] != profile.get("provider"):
            profile = {}
        data[section] = deep_merge(profile, inline) | {"profile": block["profile"]}
    return data


_PATH_FIELDS: dict[str, tuple[str, ...]] = {
    "paths": (
        "data_dir",
        "models_dir",
        "competency_model_file",
        "workflows_file",
        "forms_file",
        "prompts_file",
        "scoring_file",
    ),
    "security": ("seed_users_file",),
    "seed": ("employees_file", "evaluations_file"),
    "assistant": ("knowledge_base_dir", "faq_file", "index_file"),
}


def _resolve_paths(settings: Settings, root: Path) -> Settings:
    for section, fields in _PATH_FIELDS.items():
        block = getattr(settings, section)
        for name in fields:
            value = getattr(block, name)
            if isinstance(value, Path) and not value.is_absolute():
                setattr(block, name, (root / value).resolve())
    return settings


def resolve_path(value: str | Path, root: Path | None = None) -> Path:
    """Resolve a (possibly relative) path from component ``params`` against the project root."""
    path = Path(value)
    return path if path.is_absolute() else ((root or project_root()) / path).resolve()


def load_settings(
    config_dir: Path | None = None,
    environment: str | None = None,
    overrides: dict[str, Any] | None = None,
    environ: dict[str, str] | None = None,
) -> Settings:
    """Build validated :class:`Settings` from the layered YAML configuration."""
    env_vars = os.environ if environ is None else environ
    config_dir = Path(config_dir or env_vars.get(CONFIG_DIR_ENV) or project_root() / "config").resolve()
    data = read_yaml(config_dir / "base.yaml")

    env_name = environment or env_vars.get(ENV_SELECTOR) or data.get("app", {}).get("environment", "dev")
    env_file = config_dir / "environments" / f"{env_name}.yaml"
    if env_file.is_file():
        data = deep_merge(data, read_yaml(env_file))
    data = deep_merge(data, {"app": {"environment": env_name}})

    data = deep_merge(data, env_overrides(env_vars))
    if overrides:
        data = deep_merge(data, overrides)
    data = _apply_profiles(data, config_dir)

    try:
        settings = Settings.model_validate(data)
    except ValueError as exc:
        raise ConfigurationError(f"Invalid configuration: {exc}") from exc
    return _resolve_paths(settings, config_dir.parent)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Process-wide cached settings (call ``get_settings.cache_clear()`` to reload)."""
    return load_settings()
