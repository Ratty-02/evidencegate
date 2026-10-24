import pytest

from app import config, db
from app.main import app
from app.web.deps import current_user

TEST_USER = {"id": 1, "email": "tester@example.com"}


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path, monkeypatch):
    """Each test runs in mock mode with a temporary database and a signed-in user.

    Tests that need real sign-in remove this override themselves (see test_auth.py).
    """
    monkeypatch.setattr(config, "PAYPAL_MOCK", True)
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
    app.dependency_overrides[current_user] = lambda: TEST_USER
    yield
    app.dependency_overrides.pop(current_user, None)
