import pytest

from app.rules import paypal_evidence as pe
from app.rules.paypal_evidence import EvidenceFile, check_submission

OPEN_DISPUTE = {
    "status": "WAITING_FOR_SELLER_RESPONSE",
    "links": [{"rel": "provide-evidence"}, {"rel": "detail"}],
    "reason": "ITEM_NOT_RECEIVED",
}


def codes(result):
    return [i.code for i in result.issues]


def test_valid_submission_passes():
    result = check_submission(OPEN_DISPUTE, ["RECEIPT_OF_MERCHANDISE"], [EvidenceFile("proof.pdf", 1000)])
    assert result.ok


def test_closed_dispute_is_blocked():
    dispute = {**OPEN_DISPUTE, "status": "RESOLVED"}
    assert "STATUS_NOT_ACTIONABLE" in codes(check_submission(dispute, ["OTHER"], []))


def test_missing_evidence_link_is_blocked():
    dispute = {**OPEN_DISPUTE, "links": [{"rel": "detail"}]}
    assert "EVIDENCE_LINK_MISSING" in codes(check_submission(dispute, ["OTHER"], []))


def test_empty_submission_is_blocked():
    assert "EMPTY_SUBMISSION" in codes(check_submission(OPEN_DISPUTE, [], []))


def test_disallowed_file_type_is_blocked():
    result = check_submission(OPEN_DISPUTE, ["OTHER"], [EvidenceFile("notes.docx", 100)])
    assert "FILE_TYPE_NOT_ALLOWED" in codes(result)


def test_file_over_10mb_is_blocked():
    big = EvidenceFile("scan.png", pe.MAX_FILE_BYTES + 1)
    assert "FILE_TOO_LARGE" in codes(check_submission(OPEN_DISPUTE, ["OTHER"], [big]))


def test_case_over_50mb_is_blocked():
    files = [EvidenceFile(f"p{i}.pdf", 9 * 1024 * 1024) for i in range(6)]  # 54 MB total
    assert "CASE_TOO_LARGE" in codes(check_submission(OPEN_DISPUTE, ["OTHER"], files))


def test_missing_required_evidence_type_is_blocked(monkeypatch):
    monkeypatch.setitem(pe.REQUIRED_EVIDENCE, "ITEM_NOT_RECEIVED", {"RECEIPT_OF_MERCHANDISE"})
    result = check_submission(OPEN_DISPUTE, ["OTHER"], [EvidenceFile("a.pdf", 10)])
    assert "MISSING_EVIDENCE_TYPE" in codes(result)


def test_required_evidence_type_present_passes(monkeypatch):
    monkeypatch.setitem(pe.REQUIRED_EVIDENCE, "ITEM_NOT_RECEIVED", {"RECEIPT_OF_MERCHANDISE"})
    result = check_submission(OPEN_DISPUTE, ["RECEIPT_OF_MERCHANDISE"], [EvidenceFile("a.pdf", 10)])
    assert result.ok
