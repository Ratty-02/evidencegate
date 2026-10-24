import json
import os

import httpx
import pytest

from app.paypal import client as paypal_client
from app.paypal.client import PayPalError, RealPayPalClient

SECRET = "super-secret-value"


def token_response(token="tok-123", expires_in=3000):
    return httpx.Response(200, json={"access_token": token, "expires_in": expires_in})


def make_client(handler, **kwargs):
    return RealPayPalClient(client_id="cid", client_secret=SECRET, env="sandbox",
                            transport=httpx.MockTransport(handler), **kwargs)


def test_token_uses_basic_auth_and_client_credentials():
    seen = {}

    def handler(request):
        seen["auth"] = request.headers["Authorization"]
        seen["body"] = request.content.decode()
        seen["url"] = str(request.url)
        return token_response()

    token = make_client(handler).access_token()
    assert token == "tok-123"
    assert seen["auth"].startswith("Basic ")
    assert "grant_type=client_credentials" in seen["body"]
    assert seen["url"] == "https://api-m.sandbox.paypal.com/v1/oauth2/token"


def test_token_is_cached_until_near_expiry():
    calls = {"token": 0}

    def handler(request):
        if request.url.path == "/v1/oauth2/token":
            calls["token"] += 1
            return token_response(expires_in=3000)
        return httpx.Response(200, json={})

    client = make_client(handler)
    client.access_token()
    client.access_token()
    assert calls["token"] == 1


def test_missing_credentials_raise_clear_error():
    client = RealPayPalClient(client_id="", client_secret="", env="sandbox",
                              transport=httpx.MockTransport(lambda r: httpx.Response(500)))
    with pytest.raises(PayPalError, match="not set in .env"):
        client.access_token()


def test_retries_transient_errors_then_succeeds(monkeypatch):
    monkeypatch.setattr(paypal_client.time, "sleep", lambda s: None)
    attempts = {"list": 0}

    def handler(request):
        if request.url.path == "/v1/oauth2/token":
            return token_response()
        attempts["list"] += 1
        if attempts["list"] < 3:
            return httpx.Response(503, text="busy")
        return httpx.Response(200, json={"items": []})

    assert make_client(handler).list_disputes() == {"items": []}
    assert attempts["list"] == 3


def test_error_message_never_contains_secret():
    def handler(request):
        if request.url.path == "/v1/oauth2/token":
            return httpx.Response(401, text="invalid_client")
        return httpx.Response(401, text="unauthorized")

    with pytest.raises(PayPalError) as exc:
        make_client(handler).access_token()
    assert SECRET not in str(exc.value)


def test_invalid_env_is_rejected():
    with pytest.raises(ValueError):
        RealPayPalClient(client_id="a", client_secret="b", env="staging")


@pytest.mark.skipif(not os.getenv("RUN_LIVE"), reason="set RUN_LIVE=1 to call the PayPal sandbox")
def test_live_sandbox_token_and_listing():
    client = RealPayPalClient()
    assert client.access_token()
    listing = client.list_disputes()
    assert isinstance(listing, dict)
