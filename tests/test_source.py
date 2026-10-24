from app.paypal.source import RealDisputeSource, normalize_dispute

RAW = {
    "dispute_id": "PP-D-1",
    "status": "WAITING_FOR_SELLER_RESPONSE",
    "reason": "ITEM_NOT_RECEIVED",
    "dispute_amount": {"value": "49.00", "currency_code": "USD"},
    "disputed_transactions": [{"seller_transaction_id": "TXN-A"}],
    "seller_response_due_date": "2026-11-02T00:00:00Z",
    "links": [{"rel": "provide-evidence", "href": "x", "method": "POST"}],
}


class FakeClient:
    def list_disputes(self):
        return {"items": [RAW]}

    def get_dispute(self, dispute_id):
        return RAW


def test_normalizes_real_shape():
    d = normalize_dispute(RAW)
    assert d["id"] == "PP-D-1"
    assert d["amount"] == "49.00"
    assert d["currency"] == "USD"
    assert d["deadline"] == "2026-11-02"
    assert d["record_ids"] == ["TXN-A"]


def test_missing_deadline_is_none():
    raw = {k: v for k, v in RAW.items() if k != "seller_response_due_date"}
    assert normalize_dispute(raw)["deadline"] is None


def test_source_lists_and_gives_no_paypal_records():
    src = RealDisputeSource(FakeClient())
    disputes = src.list_disputes()
    assert len(disputes) == 1
    assert src.get_records(disputes[0]) == {}
