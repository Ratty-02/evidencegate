"""SQLite storage: drafts, approvals, merchant records, and webhook events.

Drafts are stored as the model's JSON output; the gate is re-run whenever a
draft is loaded, so checks always reflect current rules and records.
Approvals are an audit record: action, request ID, time, and PayPal's response.
Merchant records are the tracking and delivery facts a merchant supplies.
Webhook events are stored after PayPal's signature check passes.
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
CREATE TABLE IF NOT EXISTS drafts (
    dispute_id TEXT PRIMARY KEY,
    draft_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS approvals (
    dispute_id TEXT PRIMARY KEY,
    action TEXT NOT NULL,
    request_id TEXT NOT NULL,
    approved_at TEXT NOT NULL,
    paypal_response TEXT
);
CREATE TABLE IF NOT EXISTS records (
    dispute_id TEXT NOT NULL,
    record_id TEXT NOT NULL,
    field TEXT NOT NULL,
    value TEXT NOT NULL,
    PRIMARY KEY (dispute_id, record_id, field)
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
        conn.executescript(SCHEMA)  # idempotent; keeps every connection schema-safe
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with _db():
        pass


def save_draft(dispute_id: str, draft: Draft) -> None:
    with _db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO drafts (dispute_id, draft_json, created_at) VALUES (?, ?, ?)",
            (dispute_id, draft.model_dump_json(), _now()),
        )


def get_draft(dispute_id: str) -> Draft | None:
    with _db() as conn:
        row = conn.execute(
            "SELECT draft_json FROM drafts WHERE dispute_id = ?", (dispute_id,)
        ).fetchone()
    return Draft.model_validate_json(row["draft_json"]) if row else None


def save_approval(dispute_id: str, action: str, request_id: str, paypal_response: dict | None) -> None:
    with _db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO approvals "
            "(dispute_id, action, request_id, approved_at, paypal_response) VALUES (?, ?, ?, ?, ?)",
            (dispute_id, action, request_id, _now(),
             json.dumps(paypal_response) if paypal_response is not None else None),
        )


def get_approval(dispute_id: str) -> dict | None:
    with _db() as conn:
        row = conn.execute(
            "SELECT action, request_id, approved_at, paypal_response FROM approvals WHERE dispute_id = ?",
            (dispute_id,),
        ).fetchone()
    if row is None:
        return None
    return {
        "action": row["action"],
        "request_id": row["request_id"],
        "approved_at": row["approved_at"],
        "paypal_response": json.loads(row["paypal_response"]) if row["paypal_response"] else None,
    }


def delete_approval(dispute_id: str) -> None:
    with _db() as conn:
        conn.execute("DELETE FROM approvals WHERE dispute_id = ?", (dispute_id,))


def replace_records(dispute_id: str, mapping: dict[str, dict[str, str]]) -> None:
    with _db() as conn:
        conn.execute("DELETE FROM records WHERE dispute_id = ?", (dispute_id,))
        conn.executemany(
            "INSERT INTO records (dispute_id, record_id, field, value) VALUES (?, ?, ?, ?)",
            [(dispute_id, rid, field, value)
             for rid, fields in mapping.items() for field, value in fields.items()],
        )


def get_records(dispute_id: str) -> dict[str, dict[str, str]]:
    with _db() as conn:
        rows = conn.execute(
            "SELECT record_id, field, value FROM records WHERE dispute_id = ? ORDER BY record_id, field",
            (dispute_id,),
        ).fetchall()
    out: dict[str, dict[str, str]] = {}
    for r in rows:
        out.setdefault(r["record_id"], {})[r["field"]] = r["value"]
    return out


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
