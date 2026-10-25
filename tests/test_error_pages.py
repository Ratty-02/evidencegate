from fastapi.testclient import TestClient

from app.main import app
from app.paypal.client import PayPalError
from app.web import routes


def test_html_error_is_a_friendly_page():
    r = TestClient(app).get("/disputes/PP-NOPE", headers={"accept": "text/html"})
    assert r.status_code == 404
    assert "could not find" in r.text.lower()


def test_api_error_stays_json():
    r = TestClient(app).get("/disputes/PP-NOPE", headers={"accept": "application/json"})
    assert r.status_code == 404
    assert r.json() == {"detail": "no dispute PP-NOPE"}


def test_inbox_shows_a_friendly_message_when_paypal_fails(monkeypatch):
    def boom():
        raise PayPalError("HTTP 503")
    monkeypatch.setattr(routes._mock_source, "list_disputes", boom)
    r = TestClient(app).get("/disputes")
    assert r.status_code == 200
    assert "Could not load disputes from PayPal" in r.text
