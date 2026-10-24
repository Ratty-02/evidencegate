import httpx

from app.paypal.client import RealPayPalClient


def test_scopes_are_read_from_token_response():
    def handler(request):
        return httpx.Response(200, json={
            "access_token": "t",
            "expires_in": 3000,
            "scope": "https://uri.paypal.com/services/payments/payment "
                     "https://uri.paypal.com/services/disputes/read-buyer",
        })

    client = RealPayPalClient(client_id="c", client_secret="s", env="sandbox",
                              transport=httpx.MockTransport(handler))
    client.access_token()
    assert len(client.scopes) == 2
    assert any("disputes" in s for s in client.scopes)
