import re
import time

from fastapi.testclient import TestClient

from app import auth, config, db
from app.main import app
from app.web.deps import current_user

CREDS = {"email": "owner@example.com", "password": "longpassword"}
TOKEN_RE = re.compile(r"token=([A-Za-z0-9_\-]+)")


def _real_auth():
    app.dependency_overrides.pop(current_user, None)


def _verified_user(email="owner@example.com"):
    """Create and verify an account directly, skipping the email step."""
    return db.create_user(email, auth.hash_password(CREDS["password"]), verified=True)


def test_repeated_failures_lock_sign_in(monkeypatch):
    _real_auth()
    _verified_user()
    now = time.time()
    for _ in range(config.LOGIN_MAX_FAILURES):
        db.record_login_failure(CREDS["email"], now)
    r = TestClient(app).post("/login", data=CREDS, follow_redirects=False)
    assert r.status_code == 429
    assert "Too many failed" in r.text


def test_old_failures_outside_the_window_do_not_count():
    _real_auth()
    _verified_user()
    old = time.time() - config.LOGIN_WINDOW_SECONDS - 60
    for _ in range(config.LOGIN_MAX_FAILURES):
        db.record_login_failure(CREDS["email"], old)
    assert TestClient(app).post("/login", data=CREDS, follow_redirects=False).status_code == 303


def test_successful_sign_in_clears_failures():
    _real_auth()
    _verified_user()
    db.record_login_failure(CREDS["email"], time.time())
    TestClient(app).post("/login", data=CREDS, follow_redirects=False)
    assert db.count_login_failures(CREDS["email"], 0) == 0


def test_verification_link_works_once():
    _real_auth()
    client = TestClient(app)
    client.post("/signup", data=CREDS, follow_redirects=False)
    token = TOKEN_RE.search(client.post("/resend-verification", data={"email": CREDS["email"]}).text).group(1)
    assert client.get(f"/verify?token={token}", follow_redirects=False).status_code == 303
    assert client.get(f"/verify?token={token}", follow_redirects=False).status_code == 400


def test_expired_verification_link_is_refused():
    _real_auth()
    user = db.create_user("late@example.com", auth.hash_password(CREDS["password"]))
    raw, digest = auth.new_token()
    db.create_auth_token(digest, user["id"], "verify", expires_at=0)
    assert TestClient(app).get(f"/verify?token={raw}", follow_redirects=False).status_code == 400


def test_forgot_password_does_not_reveal_accounts():
    _real_auth()
    _verified_user()
    known = TestClient(app).post("/forgot", data={"email": CREDS["email"]})
    unknown = TestClient(app).post("/forgot", data={"email": "nobody@example.com"})
    assert known.status_code == unknown.status_code == 200
    assert "token=" in known.text
    assert "token=" not in unknown.text


def test_password_reset_flow():
    _real_auth()
    _verified_user()
    client = TestClient(app)
    token = TOKEN_RE.search(client.post("/forgot", data={"email": CREDS["email"]}).text).group(1)

    assert client.get(f"/reset?token={token}").status_code == 200
    r = client.post("/reset", data={"token": token, "password": "brandnewpass"}, follow_redirects=False)
    assert r.status_code == 303

    assert TestClient(app).post("/login", data={"email": CREDS["email"], "password": "brandnewpass"},
                                follow_redirects=False).status_code == 303
    assert TestClient(app).post("/login", data=CREDS, follow_redirects=False).status_code == 401


def test_reset_token_works_once():
    _real_auth()
    _verified_user()
    client = TestClient(app)
    token = TOKEN_RE.search(client.post("/forgot", data={"email": CREDS["email"]}).text).group(1)
    client.post("/reset", data={"token": token, "password": "brandnewpass"}, follow_redirects=False)
    r = client.post("/reset", data={"token": token, "password": "anotherpass"}, follow_redirects=False)
    assert r.status_code == 400


def test_reset_rejects_short_password():
    _real_auth()
    _verified_user()
    client = TestClient(app)
    token = TOKEN_RE.search(client.post("/forgot", data={"email": CREDS["email"]}).text).group(1)
    r = client.post("/reset", data={"token": token, "password": "short"}, follow_redirects=False)
    assert r.status_code == 400
    assert "at least 8" in r.text


def test_unverified_account_with_valid_cookie_is_still_blocked():
    _real_auth()
    user = db.create_user("pending@example.com", auth.hash_password(CREDS["password"]), verified=False)
    client = TestClient(app)
    client.cookies.set(auth.COOKIE_NAME, auth.make_session_token(user["id"]))
    r = client.get("/disputes", follow_redirects=False)
    assert r.status_code == 303
    assert "/login?error=" in r.headers["location"]
