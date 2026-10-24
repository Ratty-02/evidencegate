import pytest

from app import db
from app.ai.schemas import Draft, DraftClaim


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "t.db"))
    db.init_db()


DRAFT = Draft(
    evidence_types=["PROOF_OF_DELIVERY"],
    response_text="Delivered.",
    claims=[DraftClaim(statement="Delivered.", record_id="TRK-1001", field="status", value="DELIVERED")],
    recommendation="FIGHT", reason="Delivered.",
)


def test_draft_round_trips():
    db.save_draft("PP-R-0001", DRAFT)
    assert db.get_draft("PP-R-0001") == DRAFT


def test_missing_draft_returns_none():
    assert db.get_draft("PP-R-9999") is None


def test_approval_round_trips_with_paypal_response():
    db.save_approval("PP-R-0001", "SUBMIT_EVIDENCE", "req-1", {"links": []})
    record = db.get_approval("PP-R-0001")
    assert record["request_id"] == "req-1"
    assert record["paypal_response"] == {"links": []}


def test_approval_without_paypal_response_is_none():
    db.save_approval("PP-R-0001", "SUBMIT_EVIDENCE", "req-2", None)
    assert db.get_approval("PP-R-0001")["paypal_response"] is None


def test_delete_approval():
    db.save_approval("PP-R-0001", "SUBMIT_EVIDENCE", "req-3", None)
    db.delete_approval("PP-R-0001")
    assert db.get_approval("PP-R-0001") is None


def test_non_sqlite_url_is_rejected():
    with pytest.raises(ValueError):
        db._resolve("postgresql://localhost/x")
