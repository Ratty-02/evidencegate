"""Parse merchant-supplied records pasted as CSV.

Format: header exactly `record_id,field,value`, one fact per row.
Example:
    record_id,field,value
    TRK-1001,status,DELIVERED
    TRK-1001,delivered_on,2026-10-06
"""
import csv
import io
import re

MAX_ROWS = 500
MAX_VALUE_LENGTH = 200
HEADER = ["record_id", "field", "value"]
RECORD_ID = re.compile(r"^[A-Za-z0-9_\-]{1,64}$")
FIELD = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


def parse_records_csv(text: str) -> dict[str, dict[str, str]]:
    if not text or not text.strip():
        raise ValueError("paste CSV with the header record_id,field,value")
    reader = csv.DictReader(io.StringIO(text.strip()))
    if reader.fieldnames is None or [h.strip() for h in reader.fieldnames] != HEADER:
        raise ValueError("the header must be exactly record_id,field,value")

    records: dict[str, dict[str, str]] = {}
    count = 0
    for line_no, row in enumerate(reader, start=2):
        count += 1
        if count > MAX_ROWS:
            raise ValueError(f"at most {MAX_ROWS} rows are allowed")
        rid = (row.get("record_id") or "").strip()
        field = (row.get("field") or "").strip()
        value = (row.get("value") or "").strip()
        if not RECORD_ID.match(rid):
            raise ValueError(f"line {line_no}: invalid record_id {rid!r}")
        if not FIELD.match(field):
            raise ValueError(f"line {line_no}: invalid field {field!r} (lowercase letters, digits, underscores)")
        if not value:
            raise ValueError(f"line {line_no}: value is empty")
        if len(value) > MAX_VALUE_LENGTH:
            raise ValueError(f"line {line_no}: value is longer than {MAX_VALUE_LENGTH} characters")
        records.setdefault(rid, {})[field] = value

    if not records:
        raise ValueError("no data rows found under the header")
    return records
