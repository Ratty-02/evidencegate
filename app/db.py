"""SQLite storage.

Merchant workspaces are scoped by user_id (drafts, approvals, records).
Accounts hold verification and login state. Auth tokens and login attempts
are stored hashed or as counts, never as raw secrets. PayPal credentials are
stored encrypted (see app/secrets_box.py). Webhook events are platform-wide.

If an older single-workspace database is found, startup stops with a clear message.
"""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from app import config
from app.ai.schemas import Draft

PREFIX = "sqlite:///"


def _resolve(url: str) -> str:
    if not url.startswith(PREFIX):
        raise ValueError(f"only sqlite DATABASE_URL is supported, got {url!r}")
    return url[len(PREFIX):]


DB_PATH = _resolve(config.DATABASE_URL)

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    email_verified INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS drafts (
    user_id INTEGER NOT NULL,
    dispute_id TEXT NOT NULL,
    draft_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (user_id, dispute_id)
);
CREATE TABLE IF NOT EXISTS approvals (
    user_id INTEGER NOT NULL,
    dispute_id TEXT NOT NULL,
    action TEXT NOT NULL,
    request_id TEXT NOT NULL,
    approved_at TEXT NOT NULL,
    paypal_response TEXT,
    PRIMARY KEY (user_id, dispute_id)
);
CREATE TABLE IF NOT EXISTS records (
    user_id INTEGER NOT NULL,
    dispute_id TEXT NOT NULL,
    record_id TEXT NOT NULL,
    field TEXT NOT NULL,
    value TEXT NOT NULL,
    PRIMARY KEY (user_id, dispute_id, record_id, field)
);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    dispute_id TEXT,
    received_at TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS auth_tokens (
    token_hash TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    purpose TEXT NOT NULL,
    expires_at REAL NOT NULL,
    used INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS login_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT NOT NULL,
    at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS paypal_credentials (
    user_id INTEGER PRIMARY KEY,
    env TEXT NOT NULL,
    client_id_enc TEXT NOT NULL,
    secret_enc TEXT NOT NULL,
    client_hint TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def _db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(SCHEMA)  # idempotent
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with _db() as conn:
        draft_cols = {row["name"] for row in conn.execute("PRAGMA table_info(drafts)")}
        if "user_id" not in draft_cols:
            raise RuntimeError(
                "evidencegate.db uses the old single-workspace format. Delete the file "
                "(this clears local drafts, approvals, and records) and restart the app."
            )
        user_cols = {row["name"] for row in conn.execute("PRAGMA table_info(users)")}
        if "email_verified" not in user_cols:
            # Accounts created before verification existed stay usable.
            conn.execute("ALTER TABLE users ADD COLUMN email_verified INTEGER NOT NULL DEFAULT 1")


# ---- users ----

def create_user(email: str, password_hash: str, verified: bool = False) -> dict:
    try:
        with _db() as conn:
            cur = conn.execute(
                "INSERT INTO users (email, password_hash, email_verified, created_at) VALUES (?, ?, ?, ?)",
                (email, password_hash, 1 if verified else 0, _now()),
            )
            user_id = cur.lastrowid
    except sqlite3.IntegrityError:
        raise ValueError("an account with that email already exists")
    return {"id": user_id, "email": email, "email_verified": bool(verified)}


def get_user_by_email(email: str) -> dict | None:
    """Includes password_hash. Only the sign-in check should use this."""
    with _db() as conn:
        row = conn.execute(
            "SELECT id, email, password_hash, email_verified FROM users WHERE email = ?", (email,)
        ).fetchone()
    return dict(row) if row else None


def get_user(user_id: int) -> dict | None:
    with _db() as conn:
        row = conn.execute(
            "SELECT id, email, email_verified FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    return dict(row) if row else None


def set_email_verified(user_id: int) -> None:
    with _db() as conn:
        conn.execute("UPDATE users SET email_verified = 1 WHERE id = ?", (user_id,))


def update_password(user_id: int, password_hash: str) -> None:
    with _db() as conn:
        conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (password_hash, user_id))


# ---- one-time tokens (verification and password reset) ----

def create_auth_token(token_hash: str, user_id: int, purpose: str, expires_at: float) -> None:
    with _db() as conn:
        conn.execute(
            "INSERT INTO auth_tokens (token_hash, user_id, purpose, expires_at, used) VALUES (?, ?, ?, ?, 0)",
            (token_hash, user_id, purpose, expires_at),
        )


def _token_user(conn, token_hash: str, purpose: str, now: float) -> int | None:
    row = conn.execute(
        "SELECT user_id, expires_at, used FROM auth_tokens WHERE token_hash = ? AND purpose = ?",
        (token_hash, purpose),
    ).fetchone()
    if row is None or row["used"] or row["expires_at"] < now:
        return None
    return row["user_id"]


def peek_auth_token(token_hash: str, purpose: str, now: float) -> int | None:
    with _db() as conn:
        return _token_user(conn, token_hash, purpose, now)


def consume_auth_token(token_hash: str, purpose: str, now: float) -> int | None:
    """Valid once: returns the user id and marks the token used."""
    with _db() as conn:
        user_id = _token_user(conn, token_hash, purpose, now)
        if user_id is not None:
            conn.execute("UPDATE auth_tokens SET used = 1 WHERE token_hash = ?", (token_hash,))
        return user_id


# ---- sign-in throttling ----

def record_login_failure(key: str, now: float) -> None:
    with _db() as conn:
        conn.execute("INSERT INTO login_attempts (key, at) VALUES (?, ?)", (key, now))


def count_login_failures(key: str, since: float) -> int:
    with _db() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM login_attempts WHERE key = ? AND at >= ?", (key, since)
        ).fetchone()
    return int(row["n"])


def clear_login_failures(key: str) -> None:
    with _db() as conn:
        conn.execute("DELETE FROM login_attempts WHERE key = ?", (key,))


# ---- per-merchant PayPal credentials (encrypted) ----

def save_paypal_credentials(user_id: int, env: str, client_id_enc: str, secret_enc: str,
                            hint: str, updated_at: str) -> None:
    with _db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO paypal_credentials "
            "(user_id, env, client_id_enc, secret_enc, client_hint, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, env, client_id_enc, secret_enc, hint, updated_at),
        )


def get_paypal_credentials(user_id: int) -> dict | None:
    with _db() as conn:
        row = conn.execute(
            "SELECT env, client_id_enc, secret_enc, client_hint, updated_at FROM paypal_credentials "
            "WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    return dict(row) if row else None


def delete_paypal_credentials(user_id: int) -> None:
    with _db() as conn:
        conn.execute("DELETE FROM paypal_credentials WHERE user_id = ?", (user_id,))


# ---- per-user workspace ----

def save_draft(user_id: int, dispute_id: str, draft: Draft) -> None:
    with _db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO drafts (user_id, dispute_id, draft_json, created_at) VALUES (?, ?, ?, ?)",
            (user_id, dispute_id, draft.model_dump_json(), _now()),
        )


def get_draft(user_id: int, dispute_id: str) -> Draft | None:
    with _db() as conn:
        row = conn.execute(
            "SELECT draft_json FROM drafts WHERE user_id = ? AND dispute_id = ?",
            (user_id, dispute_id),
        ).fetchone()
    return Draft.model_validate_json(row["draft_json"]) if row else None


def save_approval(user_id: int, dispute_id: str, action: str, request_id: str,
                  paypal_response: dict | None) -> None:
    with _db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO approvals "
            "(user_id, dispute_id, action, request_id, approved_at, paypal_response) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, dispute_id, action, request_id, _now(),
             json.dumps(paypal_response) if paypal_response is not None else None),
        )


def get_approval(user_id: int, dispute_id: str) -> dict | None:
    with _db() as conn:
        row = conn.execute(
            "SELECT action, request_id, approved_at, paypal_response FROM approvals "
            "WHERE user_id = ? AND dispute_id = ?",
            (user_id, dispute_id),
        ).fetchone()
    if row is None:
        return None
    return {
        "action": row["action"],
        "request_id": row["request_id"],
        "approved_at": row["approved_at"],
        "paypal_response": json.loads(row["paypal_response"]) if row["paypal_response"] else None,
    }


def delete_approval(user_id: int, dispute_id: str) -> None:
    with _db() as conn:
        conn.execute("DELETE FROM approvals WHERE user_id = ? AND dispute_id = ?", (user_id, dispute_id))


def replace_records(user_id: int, dispute_id: str, mapping: dict[str, dict[str, str]]) -> None:
    with _db() as conn:
        conn.execute("DELETE FROM records WHERE user_id = ? AND dispute_id = ?", (user_id, dispute_id))
        conn.executemany(
            "INSERT INTO records (user_id, dispute_id, record_id, field, value) VALUES (?, ?, ?, ?, ?)",
            [(user_id, dispute_id, rid, field, value)
             for rid, fields in mapping.items() for field, value in fields.items()],
        )


def get_records(user_id: int, dispute_id: str) -> dict[str, dict[str, str]]:
    with _db() as conn:
        rows = conn.execute(
            "SELECT record_id, field, value FROM records WHERE user_id = ? AND dispute_id = ? "
            "ORDER BY record_id, field",
            (user_id, dispute_id),
        ).fetchall()
    out: dict[str, dict[str, str]] = {}
    for r in rows:
        out.setdefault(r["record_id"], {})[r["field"]] = r["value"]
    return out


# ---- platform events ----

def save_event(event_type: str, dispute_id: str | None, payload: dict) -> None:
    with _db() as conn:
        conn.execute(
            "INSERT INTO events (event_type, dispute_id, received_at, payload_json) VALUES (?, ?, ?, ?)",
            (event_type, dispute_id, _now(), json.dumps(payload)),
        )


def list_events(limit: int = 20) -> list[dict]:
    with _db() as conn:
        rows = conn.execute(
            "SELECT id, event_type, dispute_id, received_at FROM events ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]
