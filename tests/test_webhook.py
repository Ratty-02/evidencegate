from fastapi.testclient import TestClient

from app import db
from app.main import app
from app.web.routes import get_verifier

EVENT = {"event_type": "CUSTOMER.DISPUTE.CREATED", "resource": {"dispute_id": "PP-D-9"}}


class FakeVerifier:
    def __init__(self, ok):
        self.ok = ok
        self.calls = []

    def verify_webhook_signature(self, headers, event, webhook_id):
        self.calls.append((headers, event, webhook_id))
        return self.ok


def test_mock_mode_refuses_webhooks():
    r = TestClient(app).post("/webhooks/paypal", json=EVENT)
    assert r.status_code == 503


def test_verified_event_is_stored():
    app.dependency_overrides[get_verifier] = lambda: FakeVerifier(True)
    try:
        r = TestClient(app).post("/webhooks/paypal", json=EVENT, headers={"PAYPAL-TRANSMISSION-ID": "abc"})
        assert r.status_code == 200
        latest = db.list_events()[0]
        assert latest["event_type"] == "CUSTOMER.DISPUTE.CREATED"
        assert latest["dispute_id"] == "PP-D-9"
    finally:
        app.dependency_overrides.clear()


def test_unverified_event_is_rejected_and_not_stored():
    app.dependency_overrides[get_verifier] = lambda: FakeVerifier(False)
    try:
        r = TestClient(app).post("/webhooks/paypal", json=EVENT)
        assert r.status_code == 403
        assert db.list_events() == []
    finally:
        app.dependency_overrides.clear()


def test_invalid_json_is_rejected():
    app.dependency_overrides[get_verifier] = lambda: FakeVerifier(True)
    try:
        r = TestClient(app).post("/webhooks/paypal", content=b"not json",
                                 headers={"content-type": "application/json"})
        assert r.status_code == 400
    finally:
        app.dependency_overrides.clear()


def test_headers_are_passed_lowercased():
    v = FakeVerifier(True)
    app.dependency_overrides[get_verifier] = lambda: v
    try:
        TestClient(app).post("/webhooks/paypal", json=EVENT, headers={"PAYPAL-TRANSMISSION-ID": "abc"})
        assert v.calls[0][0]["paypal-transmission-id"] == "abc"
    finally:
        app.dependency_overrides.clear()
