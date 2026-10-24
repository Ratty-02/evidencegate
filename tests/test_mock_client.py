import pytest

from app.paypal.mock_client import DisputeNotFound, MockPayPalClient


def test_lists_all_fixture_disputes():
    assert len(MockPayPalClient().list_disputes()) == 3


def test_get_dispute_returns_record():
    d = MockPayPalClient().get_dispute("PP-R-0001")
    assert d["transaction_id"] == "TXN-1001"


def test_unknown_dispute_raises():
    with pytest.raises(DisputeNotFound):
        MockPayPalClient().get_dispute("PP-R-9999")


def test_get_records_returns_only_cited_records():
    client = MockPayPalClient()
    records = client.get_records(client.get_dispute("PP-R-0001"))
    assert set(records) == {"TXN-1001", "TRK-1001"}
