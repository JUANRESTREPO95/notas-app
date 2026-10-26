from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture
def settings(tmp_path):
    return Settings(
        data_dir=tmp_path / "data",
        secret_key="test-secret",
        admin_user="juan",
        admin_password="testpass123",
        timezone="America/Bogota",
        cookie_secure=False,
        app_name="Notas",
    )


@pytest.fixture
def app(settings):
    return create_app(settings)


@pytest.fixture
def client(app):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def auth(client):
    response = client.post(
        "/api/login", json={"username": "juan", "password": "testpass123"}
    )
    assert response.status_code == 200
    return client
