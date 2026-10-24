from app.ai.pipeline import build_user_message, format_report, run_draft
from app.ai.schemas import Draft, DraftClaim
from app.paypal.mock_client import MockPayPalClient


class FakeLLM:
    """Returns a fixed draft. No network calls."""

    def __init__(self, draft: Draft):
        self._draft = draft
        self.last_user_message = None

    def draft(self, system: str, user: str) -> Draft:
        self.last_user_message = user
        return self._draft


GOOD_DRAFT = Draft(
    evidence_types=["RECEIPT_OF_MERCHANDISE"],
    response_text="Delivered on 2026-10-06.",
    claims=[DraftClaim(statement="Delivered on 2026-10-06", record_id="TRK-1001",
                       field="delivered_on", value="2026-10-06")],
    recommendation="FIGHT",
    reason="Delivery is recorded before the claim.",
)

FABRICATED_DRAFT = Draft(
    evidence_types=["RECEIPT_OF_MERCHANDISE"],
    response_text="Signed for by the buyer on 2026-10-04.",
    claims=[DraftClaim(statement="Signed by buyer", record_id="TRK-1001",
                       field="signed_by", value="buyer1")],
    recommendation="FIGHT",
    reason="Signature exists.",
)


def test_supported_draft_is_ready_for_approval():
    report = run_draft("PP-R-0001", FakeLLM(GOOD_DRAFT))
    assert not report.blocked
    assert report.claims[0].status == "SUPPORTED"


def test_fabricated_claim_blocks_submission():
    report = run_draft("PP-R-0001", FakeLLM(FABRICATED_DRAFT))
    assert report.blocked
    assert report.claims[0].status == "UNSUPPORTED"


def test_closed_dispute_blocks_even_with_good_draft():
    report = run_draft("PP-R-0003", FakeLLM(GOOD_DRAFT))
    assert report.blocked
    assert any(i.code == "STATUS_NOT_ACTIONABLE" for i in report.rules.issues)


def test_model_receives_records_and_dispute():
    llm = FakeLLM(GOOD_DRAFT)
    run_draft("PP-R-0001", llm)
    assert "TRK-1001" in llm.last_user_message
    assert "PP-R-0001" in llm.last_user_message


def test_report_text_shows_blocked_state():
    text = format_report(run_draft("PP-R-0001", FakeLLM(FABRICATED_DRAFT)))
    assert "SUBMISSION BLOCKED" in text
    assert "[UNSUPPORTED]" in text


def test_user_message_is_valid_json_with_both_sections():
    import json
    client = MockPayPalClient()
    dispute = client.get_dispute("PP-R-0002")
    payload = json.loads(build_user_message(dispute, client.get_records(dispute)))
    assert set(payload) == {"dispute", "records"}
    assert "TRK-1002" in payload["records"]

