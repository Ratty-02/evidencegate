"""SQLite storage, scoped per user (multi-tenant).

Every merchant workspace is keyed by user_id: drafts, approvals, and merchant
records never cross accounts. Webhook events are recorded for the platform
and are not shown to merchants yet.

If an older single-workspace database is found, startup stops with a clear
message instead of mixing data.
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
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(drafts)")}
    if "user_id" not in columns:
        raise RuntimeError(
            "evidencegate.db uses the old single-workspace format. Delete the file "
            "(this clears local drafts, approvals, and records) and restart the app."
        )


# ---- users ----

def create_user(email: str, password_hash: str) -> dict:
    try:
        with _db() as conn:
            cur = conn.execute(
                "INSERT INTO users (email, password_hash, created_at) VALUES (?, ?, ?)",
                (email, password_hash, _now()),
            )
            user_id = cur.lastrowid
    except sqlite3.IntegrityError:
        raise ValueError("an account with that email already exists")
    return {"id": user_id, "email": email}


def get_user_by_email(email: str) -> dict | None:
    """Includes password_hash. Only the sign-in check should use this."""
    with _db() as conn:
        row = conn.execute(
            "SELECT id, email, password_hash FROM users WHERE email = ?", (email,)
        ).fetchone()
    return dict(row) if row else None


def get_user(user_id: int) -> dict | None:
    with _db() as conn:
        row = conn.execute("SELECT id, email FROM users WHERE id = ?", (user_id,)).fetchone()
    return dict(row) if row else None


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
