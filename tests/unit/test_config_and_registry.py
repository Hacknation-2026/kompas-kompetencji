"""Unit tests for configuration layering and component registry."""

from __future__ import annotations

import pytest

from kompas.core.config import deep_merge, env_overrides, load_settings
from kompas.core.exceptions import ConfigurationError
from kompas.core.registry import Registry


def test_deep_merge_preserves_nested_keys() -> None:
    base = {"a": {"x": 1, "y": 2}, "b": [1, 2]}
    merged = deep_merge(base, {"a": {"y": 99}, "b": [3]})
    assert merged == {"a": {"x": 1, "y": 99}, "b": [3]}
    assert base["a"]["y"] == 2


def test_env_overrides_parses_yaml_scalars() -> None:
    parsed = env_overrides({"KOMPAS__SERVER__PORT": "9090", "KOMPAS__APP__DEBUG": "true", "OTHER": "x"})
    assert parsed == {"server": {"port": 9090}, "app": {"debug": True}}


def test_load_settings_applies_profile_and_overrides() -> None:
    cfg = load_settings(
        environment="test",
        overrides={"llm": {"profile": "ollama"}},
        environ={},
    )
    assert cfg.llm.provider == "ollama"
    assert cfg.llm.params["model"] == "qwen2.5:7b-instruct"


def test_prod_rejects_placeholder_secret() -> None:
    with pytest.raises(ConfigurationError, match="jwt_secret"):
        load_settings(environment="prod", environ={})


def test_registry_create_filters_dependencies_and_rejects_duplicates() -> None:
    reg: Registry[object] = Registry("demo")

    @reg.register("sample")
    class Sample:
        def __init__(self, alpha: int, needed: str) -> None:
            self.alpha = alpha
            self.needed = needed

    obj = reg.create("sample", {"alpha": 5}, needed="ok", unused="ignored")
    assert isinstance(obj, Sample)
    assert obj.alpha == 5 and obj.needed == "ok"

    with pytest.raises(ConfigurationError):
        reg.register("sample")(Sample)

    with pytest.raises(ConfigurationError):
        reg.get("missing")
