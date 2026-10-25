from fastapi.testclient import TestClient

from app import db
from app.main import app


def test_sample_csv_downloads_as_csv():
    r = TestClient(app).get("/records/sample.csv")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert r.text.startswith("record_id,field,value")


def test_uploaded_file_is_saved_as_records():
    csv_bytes = b"record_id,field,value\nTRK-5,status,DELIVERED\n"
    r = TestClient(app).post("/disputes/PP-R-0001/records", data={"csv_text": ""},
                             files={"file": ("records.csv", csv_bytes, "text/csv")}, follow_redirects=False)
    assert r.status_code == 303
    assert "error=" not in r.headers["location"]
    assert "TRK-5" in db.get_records(1, "PP-R-0001")


def test_oversized_upload_is_refused():
    big = b"record_id,field,value\n" + b"TRK-1,status,DELIVERED\n" * 20000
    r = TestClient(app).post("/disputes/PP-R-0001/records", data={"csv_text": ""},
                             files={"file": ("big.csv", big, "text/csv")}, follow_redirects=False)
    assert "larger" in r.headers["location"]
