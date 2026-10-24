from fastapi.testclient import TestClient

from app import db
from app.main import app


def test_app_startup_creates_tables_and_serves_inbox(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "startup.db"))
    with TestClient(app) as client:  # runs the lifespan startup
        r = client.get("/disputes")
        assert r.status_code == 200
        assert "PP-R-0001" in r.text
