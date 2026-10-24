"""Offline stand-in for the PayPal dispute endpoints.

Returns fixture data in the same shape the app expects from the real API.
Used when PAYPAL_MOCK=true. Swap for the real client once the sandbox
response shape is confirmed.
"""
import json
from pathlib import Path

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures"


class DisputeNotFound(KeyError):
    pass


class MockPayPalClient:
    def __init__(self, fixtures_dir: Path = FIXTURES_DIR):
        disputes = json.loads((fixtures_dir / "disputes.json").read_text(encoding="utf-8"))
        self._disputes = {d["id"]: d for d in disputes}
        self._records = json.loads((fixtures_dir / "records.json").read_text(encoding="utf-8"))

    def list_disputes(self) -> list[dict]:
        return list(self._disputes.values())

    def get_dispute(self, dispute_id: str) -> dict:
        if dispute_id not in self._disputes:
            raise DisputeNotFound(dispute_id)
        return self._disputes[dispute_id]

    def get_records(self, dispute: dict) -> dict[str, dict]:
        return {rid: self._records[rid] for rid in dispute.get("record_ids", []) if rid in self._records}
