"""Adapts the real PayPal dispute responses to the shape the app uses.

Field names below are ASSUMED from PayPal's documentation and must be checked
against a real sandbox response before relying on them:
  dispute_amount, disputed_transactions[].seller_transaction_id,
  seller_response_due_date.
PayPal does not provide tracking or delivery records, so get_records() returns
an empty mapping; merchant records are added separately.
"""
from app.paypal.client import RealPayPalClient


def normalize_dispute(raw: dict) -> dict:
    amount = raw.get("dispute_amount") or {}
    transactions = raw.get("disputed_transactions") or []
    txn_ids = [t.get("seller_transaction_id") for t in transactions if t.get("seller_transaction_id")]
    due = raw.get("seller_response_due_date") or ""
    return {
        "id": raw.get("dispute_id", ""),
        "status": raw.get("status", "UNKNOWN"),
        "reason": raw.get("reason", "UNKNOWN"),
        "amount": str(amount.get("value", "0.00")),
        "currency": amount.get("currency_code", ""),
        "deadline": due[:10] or None,
        "record_ids": txn_ids,
        "links": raw.get("links", []),
    }


class RealDisputeSource:
    def __init__(self, client: RealPayPalClient):
        self.client = client

    def list_disputes(self) -> list[dict]:
        listing = self.client.list_disputes()
        items = listing.get("items") or listing.get("disputes") or []
        return [normalize_dispute(item) for item in items]

    def get_dispute(self, dispute_id: str) -> dict:
        return normalize_dispute(self.client.get_dispute(dispute_id))

    def get_records(self, dispute: dict) -> dict[str, dict]:
        return {}
