import base64

from fastapi.testclient import TestClient

from app import config
from app.main import app


def basic(user, password):
    return "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()


def test_login_required_when_password_is_set(monkeypatch):
    monkeypatch.setattr(config, "APP_PASSWORD", "s3cret")
    monkeypatch.setattr(config, "APP_USER", "admin")
    client = TestClient(app)
    assert client.get("/disputes").status_code == 401
    assert client.get("/disputes", headers={"Authorization": basic("admin", "wrong")}).status_code == 401
    assert client.get("/disputes", headers={"Authorization": basic("admin", "s3cret")}).status_code == 200


def test_open_paths_skip_login(monkeypatch):
    monkeypatch.setattr(config, "APP_PASSWORD", "s3cret")
    client = TestClient(app)
    assert client.get("/health").status_code == 200
    assert client.get("/static/style.css").status_code == 200
    assert client.get("/webhooks/paypal").status_code != 401
