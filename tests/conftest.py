import pytest
from cryptography.fernet import Fernet

from app import config, db
from app.main import app
from app.web.deps import current_user

TEST_USER = {"id": 1, "email": "tester@example.com", "email_verified": 1}


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path, monkeypatch):
    """Each test runs in mock mode with a temporary database, a test encryption key,
    and a signed-in verified user. Tests that need real sign-in remove the override."""
    monkeypatch.setattr(config, "PAYPAL_MOCK", True)
    monkeypatch.setattr(config, "CREDENTIAL_KEY", Fernet.generate_key().decode())
    monkeypatch.setattr(config, "EMAIL_MODE", "dev")
    monkeypatch.setattr(config, "APP_BASE_URL", "http://127.0.0.1:8000")
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
    app.dependency_overrides[current_user] = lambda: TEST_USER
    yield
    app.dependency_overrides.pop(current_user, None)
