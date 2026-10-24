"""Each merchant's workspace must be invisible to every other merchant."""
import pytest
from fastapi.testclient import TestClient

from app import db
from app.ai.schemas import Draft, DraftClaim
from app.main import app
from app.web.deps import current_user
from app.web.routes import get_llm


class FakeLLM:
    def __init__(self, draft):
        self._draft = draft

    def draft(self, system, user):
        return self._draft


def cites(record_id):
    return Draft(
        evidence_types=["PROOF_OF_DELIVERY"],
        response_text=f"Delivered per tracking {record_id}.",
        claims=[DraftClaim(statement=f"Delivered per tracking {record_id}.", record_id=record_id,
                           field="status", value="DELIVERED")],
        recommendation="FIGHT", reason="Delivered.",
    )


@pytest.fixture
def merchants():
    alice = db.create_user("alice@example.com", "x")
    bob = db.create_user("bob@example.com", "x")
    return alice, bob


def act_as(user):
    app.dependency_overrides[current_user] = lambda: user


def teardown_function():
    app.dependency_overrides.pop(get_llm, None)


def test_records_do_not_leak_between_merchants(merchants):
    alice, bob = merchants
    act_as(alice)
    TestClient(app).post("/disputes/PP-R-0001/records",
                         data={"csv_text": "record_id,field,value\nTRK-ALICE,status,DELIVERED\n"},
                         follow_redirects=False)
    assert "TRK-ALICE" in db.get_records(alice["id"], "PP-R-0001")
    assert db.get_records(bob["id"], "PP-R-0001") == {}


def test_drafts_and_approvals_do_not_leak(merchants):
    alice, bob = merchants
    app.dependency_overrides[get_llm] = lambda: FakeLLM(cites("TRK-1001"))

    act_as(alice)
    client = TestClient(app)
    client.post("/disputes/PP-R-0001/draft", follow_redirects=False)
    client.post("/disputes/PP-R-0001/approve", follow_redirects=False)
    assert db.get_approval(alice["id"], "PP-R-0001") is not None

    act_as(bob)
    bob_client = TestClient(app)
    assert db.get_draft(bob["id"], "PP-R-0001") is None
    assert db.get_approval(bob["id"], "PP-R-0001") is None
    assert bob_client.post("/disputes/PP-R-0001/approve", follow_redirects=False).status_code == 400
    assert "Recorded only; not yet sent to PayPal" not in bob_client.get("/disputes/PP-R-0001").text


def test_same_draft_gets_different_gate_results_per_merchant(merchants):
    alice, bob = merchants
    db.replace_records(alice["id"], "PP-R-0001", {"TRK-7777": {"status": "DELIVERED"}})
    app.dependency_overrides[get_llm] = lambda: FakeLLM(cites("TRK-7777"))

    act_as(alice)
    TestClient(app).post("/disputes/PP-R-0001/draft", follow_redirects=False)
    assert TestClient(app).post("/disputes/PP-R-0001/approve", follow_redirects=False).status_code == 303

    act_as(bob)
    TestClient(app).post("/disputes/PP-R-0001/draft", follow_redirects=False)
    assert TestClient(app).post("/disputes/PP-R-0001/approve", follow_redirects=False).status_code == 409
