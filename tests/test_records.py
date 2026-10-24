import pytest
from fastapi.testclient import TestClient

from app import db
from app.ai.pipeline import check_draft
from app.ai.schemas import Draft, DraftClaim
from app.main import app
from app.records import parse_records_csv


def test_parses_valid_csv():
    out = parse_records_csv("record_id,field,value\nTRK-1,status,DELIVERED\nTRK-1,delivered_on,2026-10-06\n")
    assert out == {"TRK-1": {"status": "DELIVERED", "delivered_on": "2026-10-06"}}


def test_rejects_wrong_header():
    with pytest.raises(ValueError, match="header"):
        parse_records_csv("id,field,value\nTRK-1,status,DELIVERED\n")


def test_rejects_bad_record_id():
    with pytest.raises(ValueError, match="invalid record_id"):
        parse_records_csv("record_id,field,value\nbad id!,status,X\n")


def test_rejects_bad_field_name():
    with pytest.raises(ValueError, match="invalid field"):
        parse_records_csv("record_id,field,value\nTRK-1,Delivered-On,X\n")


def test_rejects_empty_value():
    with pytest.raises(ValueError, match="empty"):
        parse_records_csv("record_id,field,value\nTRK-1,status,\n")


def test_rejects_empty_input():
    with pytest.raises(ValueError):
        parse_records_csv("   ")


def test_storage_round_trip():
    db.replace_records("PP-R-0001", {"TRK-9": {"status": "DELIVERED"}})
    assert db.get_records("PP-R-0001") == {"TRK-9": {"status": "DELIVERED"}}


def test_uploaded_records_back_a_claim():
    db.replace_records("PP-R-0001", {"TRK-7777": {"status": "DELIVERED"}})
    draft = Draft(
        evidence_types=["PROOF_OF_DELIVERY"],
        response_text="Delivered per tracking TRK-7777.",
        claims=[DraftClaim(statement="Delivered per tracking TRK-7777.", record_id="TRK-7777",
                           field="status", value="DELIVERED")],
        recommendation="FIGHT", reason="Delivered.",
    )
    report = check_draft("PP-R-0001", draft)
    assert report.claims[0].status == "SUPPORTED"
    assert not report.blocked


def test_upload_route_saves_and_clears_approval():
    client = TestClient(app)
    r = client.post("/disputes/PP-R-0001/records",
                    data={"csv_text": "record_id,field,value\nTRK-8888,status,DELIVERED\n"},
                    follow_redirects=False)
    assert r.status_code == 303
    assert "error=" not in r.headers["location"]
    assert "TRK-8888" in db.get_records("PP-R-0001")


def test_bad_csv_redirects_with_error():
    client = TestClient(app)
    r = client.post("/disputes/PP-R-0001/records", data={"csv_text": "wrong,header,here\n1,2,3"},
                    follow_redirects=False)
    assert r.status_code == 303
    assert "error=" in r.headers["location"]
