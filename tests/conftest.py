"""Shared pytest fixtures."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from kompas.container import AppContainer, build_container
from kompas.core.config import Settings, get_settings, load_settings
from kompas.main import create_app


@pytest.fixture(autouse=True)
def _force_test_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("KOMPAS_ENV", "test")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture()
def settings() -> Settings:
    return load_settings(environment="test", environ=dict(os.environ))


@pytest.fixture()
def container(settings: Settings) -> AppContainer:
    return build_container(settings)


@pytest.fixture()
def client(container: AppContainer) -> TestClient:
    app = create_app(container=container)
    return TestClient(app)


def auth_header(client: TestClient, username: str, password: str) -> dict[str, str]:
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

