import pytest

from app import config, db


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path, monkeypatch):
    """Every test runs in mock mode, with no login and a temporary database."""
    monkeypatch.setattr(config, "PAYPAL_MOCK", True)
    monkeypatch.setattr(config, "APP_PASSWORD", "")
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
