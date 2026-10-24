import pytest
from fastapi.testclient import TestClient

from app.ai.schemas import Draft, DraftClaim
from app.main import app
from app.web import routes
from app.web.routes import get_llm


class FakeLLM:
    def __init__(self, draft):
        self._draft = draft

    def draft(self, system, user):
        return self._draft


GOOD = Draft(
    evidence_types=["RECEIPT_OF_MERCHANDISE"],
    response_text="The item was delivered on 2026-10-06.",
    claims=[DraftClaim(statement="The item was delivered on 2026-10-06.", record_id="TRK-1001",
                       field="delivered_on", value="2026-10-06")],
    recommendation="FIGHT", reason="Delivered.",
)
FABRICATED = GOOD.model_copy(update={"claims": [
    DraftClaim(statement="The item was delivered on 2026-10-06.", record_id="TRK-1001",
               field="delivered_on", value="2026-10-01")]})
ESCALATE = Draft(evidence_types=[], response_text="Unclear.", claims=[],
                 recommendation="ESCALATE", reason="Mixed.")


@pytest.fixture
def client():
    routes.REPORTS.clear()
    routes.APPROVED.clear()
    yield TestClient(app)
    app.dependency_overrides.clear()


def use_llm(draft):
    app.dependency_overrides[get_llm] = lambda: FakeLLM(draft)


def test_inbox_lists_disputes(client):
    r = client.get("/disputes")
    assert r.status_code == 200
    assert "PP-R-0001" in r.text


def test_unknown_dispute_is_404(client):
    assert client.get("/disputes/PP-R-9999").status_code == 404


def test_approve_without_draft_is_refused(client):
    r = client.post("/disputes/PP-R-0001/approve", follow_redirects=False)
    assert r.status_code == 400


def test_good_draft_can_be_approved(client):
    use_llm(GOOD)
    client.post("/disputes/PP-R-0001/draft", follow_redirects=False)
    r = client.post("/disputes/PP-R-0001/approve", follow_redirects=False)
    assert r.status_code == 303
    page = client.get("/disputes/PP-R-0001").text
    assert "Recorded only; not yet sent to PayPal" in page


def test_blocked_draft_cannot_be_approved(client):
    use_llm(FABRICATED)
    client.post("/disputes/PP-R-0001/draft", follow_redirects=False)
    r = client.post("/disputes/PP-R-0001/approve", follow_redirects=False)
    assert r.status_code == 409


def test_closed_dispute_cannot_be_approved(client):
    use_llm(GOOD)
    client.post("/disputes/PP-R-0003/draft", follow_redirects=False)
    r = client.post("/disputes/PP-R-0003/approve", follow_redirects=False)
    assert r.status_code == 409


def test_escalate_cannot_be_approved(client):
    use_llm(ESCALATE)
    client.post("/disputes/PP-R-0002/draft", follow_redirects=False)
    r = client.post("/disputes/PP-R-0002/approve", follow_redirects=False)
    assert r.status_code == 400


def test_regenerating_draft_clears_approval(client):
    use_llm(GOOD)
    client.post("/disputes/PP-R-0001/draft", follow_redirects=False)
    client.post("/disputes/PP-R-0001/approve", follow_redirects=False)
    use_llm(GOOD)
    client.post("/disputes/PP-R-0001/draft", follow_redirects=False)
    assert "PP-R-0001" not in routes.APPROVED


def test_home_page_shows_tagline(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "Gate the" in r.text
    assert "Guesswork" in r.text
