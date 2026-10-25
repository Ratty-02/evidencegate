import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from app import config, db
from app.main import app
from app.paypal.source import RealDisputeSource
from app.secrets_box import KeyMissing, decrypt, encrypt
from app.services import credentials
from app.web import routes


def test_round_trip_and_ciphertext_differs_from_plaintext():
    token = encrypt("client-secret-123")
    assert "client-secret-123" not in token
    assert decrypt(token) == "client-secret-123"


def test_saved_credentials_are_encrypted_at_rest():
    credentials.save(1, "AbCdEfGhIjKl1234", "super-secret-value", "sandbox")
    row = db.get_paypal_credentials(1)
    assert "super-secret-value" not in row["secret_enc"]
    assert "AbCdEfGhIjKl1234" not in row["client_id_enc"]
    loaded = credentials.load(1)
    assert loaded == {"client_id": "AbCdEfGhIjKl1234", "client_secret": "super-secret-value", "env": "sandbox"}


def test_status_shows_only_a_hint():
    credentials.save(1, "AbCdEfGhIjKl1234", "super-secret-value", "sandbox")
    status = credentials.status(1)
    assert status["hint"] == "1234"
    assert "super-secret-value" not in str(status)


def test_invalid_environment_is_rejected():
    with pytest.raises(ValueError):
        credentials.save(1, "a", "b", "staging")


def test_missing_key_blocks_saving(monkeypatch):
    monkeypatch.setattr(config, "CREDENTIAL_KEY", "")
    with pytest.raises(KeyMissing):
        credentials.save(1, "a", "b", "sandbox")


def test_wrong_key_cannot_read_saved_credentials(monkeypatch):
    credentials.save(1, "AbCdEfGhIjKl1234", "super-secret-value", "sandbox")
    monkeypatch.setattr(config, "CREDENTIAL_KEY", Fernet.generate_key().decode())
    with pytest.raises(KeyMissing):
        credentials.load(1)


def test_connected_account_reads_its_own_paypal_data():
    credentials.save(1, "AbCdEfGhIjKl1234", "super-secret-value", "sandbox")
    source = routes.get_paypal({"id": 1, "email": "x", "email_verified": 1})
    assert isinstance(source, RealDisputeSource)


def test_unconnected_account_uses_demo_data():
    source = routes.get_paypal({"id": 1, "email": "x", "email_verified": 1})
    assert source is routes._mock_source


def test_settings_page_and_save_and_delete():
    client = TestClient(app)
    assert client.get("/settings/paypal").status_code == 200

    r = client.post("/settings/paypal", data={"client_id": "AbCdEfGhIjKl1234",
                                              "client_secret": "super-secret-value",
                                              "env": "sandbox"}, follow_redirects=False)
    assert r.status_code == 303
    assert db.get_paypal_credentials(1) is not None

    client.post("/settings/paypal/delete", follow_redirects=False)
    assert db.get_paypal_credentials(1) is None


def test_settings_reject_missing_fields():
    r = TestClient(app).post("/settings/paypal", data={"client_id": "", "client_secret": "x", "env": "sandbox"},
                             follow_redirects=False)
    assert r.status_code == 303
    assert "error=" in r.headers["location"]
