"""Real PayPal REST client for the sandbox (or live, when configured).

Authentication: OAuth2 client credentials. Tokens are cached until shortly
before they expire. Transient errors (429 and 5xx) are retried with backoff.
Write calls send a PayPal-Request-Id header; retries reuse the same ID so
PayPal can treat them as one request. Error messages never include the secret.

Write endpoint body shapes follow PayPal's Disputes API reference. Confirm
them against a real sandbox dispute before going live (see docs/sandbox_limits.md).
"""
import time

import httpx

from app import config

BASE_URLS = {
    "sandbox": "https://api-m.sandbox.paypal.com",
    "live": "https://api-m.paypal.com",
}
RETRY_STATUSES = {429, 500, 502, 503, 504}


class PayPalError(Exception):
    pass


class RealPayPalClient:
    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        env: str | None = None,
        transport: httpx.BaseTransport | None = None,
        max_retries: int = 2,
    ):
        self.client_id = config.PAYPAL_CLIENT_ID if client_id is None else client_id
        self.client_secret = config.PAYPAL_CLIENT_SECRET if client_secret is None else client_secret
        env = env or config.PAYPAL_ENV
        if env not in BASE_URLS:
            raise ValueError(f"PAYPAL_ENV must be 'sandbox' or 'live', got {env!r}")
        self.base_url = BASE_URLS[env]
        self.max_retries = max_retries
        self._http = httpx.Client(base_url=self.base_url, timeout=30.0, transport=transport)
        self._token: str | None = None
        self._expires_at = 0.0

    def access_token(self) -> str:
        if not self.client_id or not self.client_secret:
            raise PayPalError("PAYPAL_CLIENT_ID or PAYPAL_CLIENT_SECRET is not set in .env")
        if self._token and time.time() < self._expires_at - 60:
            return self._token
        response = self._http.post(
            "/v1/oauth2/token",
            auth=(self.client_id, self.client_secret),
            data={"grant_type": "client_credentials"},
            headers={"Accept": "application/json"},
        )
        if response.status_code != 200:
            raise PayPalError(f"token request failed: HTTP {response.status_code}")
        body = response.json()
        self._token = body["access_token"]
        self._expires_at = time.time() + int(body.get("expires_in", 3000))
        return self._token

    def _request(self, method: str, path: str, request_id: str | None = None, **kwargs) -> dict:
        for attempt in range(self.max_retries + 1):
            headers = {"Authorization": f"Bearer {self.access_token()}", "Accept": "application/json"}
            if request_id:
                headers["PayPal-Request-Id"] = request_id
            response = self._http.request(method, path, headers=headers, **kwargs)
            if response.status_code in RETRY_STATUSES and attempt < self.max_retries:
                time.sleep(2 ** attempt)
                continue
            if response.status_code >= 400:
                raise PayPalError(f"{method} {path} failed: HTTP {response.status_code} {response.text[:300]}")
            return response.json() if response.content else {}
        raise PayPalError(f"{method} {path} failed after retries")

    # Read endpoints
    def list_disputes(self, page_size: int = 10) -> dict:
        return self._request("GET", "/v1/customer/disputes", params={"page_size": page_size})

    def get_dispute(self, dispute_id: str) -> dict:
        return self._request("GET", f"/v1/customer/disputes/{dispute_id}")

    # Write endpoints
    def provide_evidence(self, dispute_id: str, evidences: list[dict], request_id: str) -> dict:
        return self._request(
            "POST",
            f"/v1/customer/disputes/{dispute_id}/provide-evidence",
            request_id=request_id,
            json={"evidences": evidences},
        )

    def accept_claim(self, dispute_id: str, reason: str, note: str, request_id: str) -> dict:
        return self._request(
            "POST",
            f"/v1/customer/disputes/{dispute_id}/accept-claim",
            request_id=request_id,
            json={"reason": reason, "note": note},
        )
