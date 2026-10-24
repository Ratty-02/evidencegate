import pytest
from fastapi.testclient import TestClient

from app import auth, config, db
from app.main import app
from app.web.deps import current_user

CREDS = {"email": "rehan@example.com", "password": "longpassword"}


@pytest.fixture
def real_auth():
    """Remove the test override so the real session check runs."""
    saved = app.dependency_overrides.pop(current_user, None)
    yield
    if saved is not None:
        app.dependency_overrides[current_user] = saved


def test_protected_page_redirects_to_login(real_auth):
    r = TestClient(app).get("/disputes", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/login"


def test_signup_signs_in_and_opens_case_board(real_auth):
    client = TestClient(app)
    assert client.post("/signup", data=CREDS, follow_redirects=False).status_code == 303
    assert client.get("/disputes").status_code == 200


def test_weak_password_is_rejected(real_auth):
    r = TestClient(app).post("/signup", data={"email": "a@b.co", "password": "short"},
                             follow_redirects=False)
    assert r.status_code == 400


def test_invalid_email_is_rejected(real_auth):
    r = TestClient(app).post("/signup", data={"email": "not-an-email", "password": "longpassword"},
                             follow_redirects=False)
    assert r.status_code == 400


def test_duplicate_email_is_rejected(real_auth):
    TestClient(app).post("/signup", data=CREDS, follow_redirects=False)
    assert TestClient(app).post("/signup", data=CREDS, follow_redirects=False).status_code == 409


def test_wrong_password_fails_and_right_one_works(real_auth):
    TestClient(app).post("/signup", data=CREDS, follow_redirects=False)
    bad = TestClient(app).post("/login", data={"email": CREDS["email"], "password": "nope-nope"},
                               follow_redirects=False)
    assert bad.status_code == 401
    assert TestClient(app).post("/login", data=CREDS, follow_redirects=False).status_code == 303


def test_email_is_case_insensitive_at_login(real_auth):
    TestClient(app).post("/signup", data=CREDS, follow_redirects=False)
    r = TestClient(app).post("/login", data={"email": "REHAN@Example.com", "password": CREDS["password"]},
                             follow_redirects=False)
    assert r.status_code == 303


def test_logout_ends_the_session(real_auth):
    client = TestClient(app)
    client.post("/signup", data=CREDS, follow_redirects=False)
    assert client.get("/disputes").status_code == 200
    client.post("/logout", follow_redirects=False)
    assert client.get("/disputes", follow_redirects=False).status_code == 303


def test_password_is_stored_hashed(real_auth):
    TestClient(app).post("/signup", data=CREDS, follow_redirects=False)
    stored = db.get_user_by_email(CREDS["email"])["password_hash"]
    assert CREDS["password"] not in stored
    assert auth.verify_password(CREDS["password"], stored)
    assert not auth.verify_password("wrong-password", stored)


def test_session_token_round_trip():
    assert auth.read_session_token(auth.make_session_token(7)) == 7


def test_tampered_token_is_rejected():
    token = auth.make_session_token(7)
    tampered = token[:-1] + ("0" if token[-1] != "0" else "1")
    assert auth.read_session_token(tampered) is None


def test_expired_token_is_rejected():
    token = auth.make_session_token(7, now=0)
    assert auth.read_session_token(token, now=config.SESSION_MAX_AGE_DAYS * 86400 + 10) is None


def test_public_paths_do_not_require_login(real_auth):
    client = TestClient(app)
    assert client.get("/health").status_code == 200
    assert client.get("/").status_code == 200
    assert client.get("/login").status_code == 200
    assert client.get("/signup").status_code == 200
    assert client.get("/static/style.css").status_code == 200
    assert client.get("/webhooks/paypal").status_code != 303
