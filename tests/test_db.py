import sqlite3

import pytest

from app import db
from app.ai.schemas import Draft, DraftClaim

DRAFT = Draft(
    evidence_types=["PROOF_OF_DELIVERY"],
    response_text="Delivered.",
    claims=[DraftClaim(statement="Delivered.", record_id="TRK-1001", field="status", value="DELIVERED")],
    recommendation="FIGHT", reason="Delivered.",
)


def test_draft_round_trips_per_user():
    db.save_draft(1, "PP-R-0001", DRAFT)
    assert db.get_draft(1, "PP-R-0001") == DRAFT
    assert db.get_draft(2, "PP-R-0001") is None


def test_approval_round_trips_with_paypal_response():
    db.save_approval(1, "PP-R-0001", "SUBMIT_EVIDENCE", "req-1", {"links": []})
    record = db.get_approval(1, "PP-R-0001")
    assert record["request_id"] == "req-1"
    assert record["paypal_response"] == {"links": []}


def test_delete_approval_only_affects_that_user():
    db.save_approval(1, "PP-R-0001", "SUBMIT_EVIDENCE", "a", None)
    db.save_approval(2, "PP-R-0001", "SUBMIT_EVIDENCE", "b", None)
    db.delete_approval(1, "PP-R-0001")
    assert db.get_approval(1, "PP-R-0001") is None
    assert db.get_approval(2, "PP-R-0001") is not None


def test_records_are_scoped_per_user():
    db.replace_records(1, "PP-R-0001", {"TRK-9": {"status": "DELIVERED"}})
    assert db.get_records(1, "PP-R-0001") == {"TRK-9": {"status": "DELIVERED"}}
    assert db.get_records(2, "PP-R-0001") == {}


def test_non_sqlite_url_is_rejected():
    with pytest.raises(ValueError):
        db._resolve("postgresql://localhost/x")


def test_old_single_workspace_database_is_refused(tmp_path, monkeypatch):
    old = tmp_path / "old.db"
    conn = sqlite3.connect(old)
    conn.execute("CREATE TABLE drafts (dispute_id TEXT PRIMARY KEY, draft_json TEXT, created_at TEXT)")
    conn.commit()
    conn.close()
    monkeypatch.setattr(db, "DB_PATH", str(old))
    with pytest.raises(RuntimeError, match="old single-workspace"):
        db.init_db()
