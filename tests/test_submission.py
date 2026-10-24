import json

import httpx
import pytest

from app.ai.pipeline import check_draft
from app.ai.schemas import Draft, DraftClaim
from app.paypal import client as paypal_client
from app.paypal.client import RealPayPalClient
from app.paypal.mock_client import MockPayPalClient
from app.services.submission import SubmissionRefused, submit_report

GOOD = Draft(
    evidence_types=["proof_of_delivery"],
    response_text="The item was delivered on 2026-10-06.",
    claims=[DraftClaim(statement="The item was delivered on 2026-10-06.", record_id="TRK-1001",
                       field="delivered_on", value="2026-10-06")],
    recommendation="FIGHT", reason="Delivered.",
)
ACCEPT = Draft(evidence_types=[], response_text="We accept this claim.", claims=[],
               recommendation="ACCEPT", reason="Parcel is still in transit.")


class FakeClient:
    def __init__(self):
        self.calls = []

    def provide_evidence(self, dispute_id, evidences, request_id):
        self.calls.append(("provide_evidence", dispute_id, evidences, request_id))
        return {"links": []}

    def accept_claim(self, dispute_id, reason, note, request_id):
        self.calls.append(("accept_claim", dispute_id, reason, note, request_id))
        return {"links": []}


def open_dispute(dispute_id="PP-R-0001"):
    return MockPayPalClient().get_dispute(dispute_id)


def test_fight_sends_normalized_evidence_with_request_id():
    report = check_draft("PP-R-0001", GOOD)
    client = FakeClient()
    submit_report(report, open_dispute(), client, request_id="req-1")
    name, dispute_id, evidences, req = client.calls[0]
    assert name == "provide_evidence"
    assert dispute_id == "PP-R-0001"
    assert evidences == [{"evidence_type": "PROOF_OF_DELIVERY",
                          "notes": "The item was delivered on 2026-10-06."}]
    assert req == "req-1"


def test_blocked_draft_never_reaches_paypal():
    bad = GOOD.model_copy(update={"response_text": "The item was delivered on 2026-10-06. Extra claim."})
    report = check_draft("PP-R-0001", bad)
    client = FakeClient()
    with pytest.raises(SubmissionRefused, match="blocked"):
        submit_report(report, open_dispute(), client, request_id="req-2")
    assert client.calls == []


def test_missing_evidence_link_is_refused():
    report = check_draft("PP-R-0001", GOOD)
    dispute = {**open_dispute(), "links": [{"rel": "detail"}]}
    client = FakeClient()
    with pytest.raises(SubmissionRefused, match="evidence link"):
        submit_report(report, dispute, client, request_id="req-3")
    assert client.calls == []


def test_human_review_is_refused():
    escalate = Draft(evidence_types=[], response_text="Unclear.", claims=[],
                     recommendation="ESCALATE", reason="Mixed.")
    report = check_draft("PP-R-0002", escalate)
    client = FakeClient()
    with pytest.raises(SubmissionRefused, match="human decision"):
        submit_report(report, open_dispute("PP-R-0002"), client, request_id="req-4")
    assert client.calls == []


def test_accept_calls_accept_claim_with_reason():
    report = check_draft("PP-R-0002", ACCEPT)
    client = FakeClient()
    submit_report(report, open_dispute("PP-R-0002"), client, request_id="req-5")
    name, dispute_id, reason, note, req = client.calls[0]
    assert name == "accept_claim"
    assert reason == "NOT_ABLE_TO_WIN"
    assert note == "Parcel is still in transit."
    assert req == "req-5"


def test_client_sends_request_id_and_body_for_evidence():
    seen = {}

    def handler(request):
        if request.url.path == "/v1/oauth2/token":
            return httpx.Response(200, json={"access_token": "t", "expires_in": 3000})
        seen["header"] = request.headers.get("PayPal-Request-Id")
        seen["body"] = json.loads(request.content)
        seen["path"] = request.url.path
        return httpx.Response(202, json={"links": []})

    client = RealPayPalClient(client_id="c", client_secret="s", env="sandbox",
                              transport=httpx.MockTransport(handler))
    client.provide_evidence("PP-D-1", [{"evidence_type": "OTHER", "notes": "x"}], request_id="abc")
    assert seen["path"] == "/v1/customer/disputes/PP-D-1/provide-evidence"
    assert seen["header"] == "abc"
    assert seen["body"] == {"evidences": [{"evidence_type": "OTHER", "notes": "x"}]}


def test_retry_reuses_the_same_request_id(monkeypatch):
    monkeypatch.setattr(paypal_client.time, "sleep", lambda s: None)
    ids = []

    def handler(request):
        if request.url.path == "/v1/oauth2/token":
            return httpx.Response(200, json={"access_token": "t", "expires_in": 3000})
        ids.append(request.headers.get("PayPal-Request-Id"))
        if len(ids) < 2:
            return httpx.Response(503, text="busy")
        return httpx.Response(202, json={})

    client = RealPayPalClient(client_id="c", client_secret="s", env="sandbox",
                              transport=httpx.MockTransport(handler))
    client.accept_claim("PP-D-1", "NOT_ABLE_TO_WIN", "note", request_id="same-id")
    assert ids == ["same-id", "same-id"]
