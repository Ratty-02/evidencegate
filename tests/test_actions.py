from app.ai.pipeline import ACCEPT_CLAIM, HUMAN_REVIEW, SUBMIT_EVIDENCE, run_draft
from app.ai.schemas import Draft, DraftClaim


class FakeLLM:
    def __init__(self, draft):
        self._draft = draft

    def draft(self, system, user):
        return self._draft


FIGHT = Draft(
    evidence_types=["transaction_details"],
    response_text="The item was delivered on 2026-10-06.",
    claims=[DraftClaim(statement="The item was delivered on 2026-10-06.", record_id="TRK-1001",
                       field="delivered_on", value="2026-10-06")],
    recommendation="FIGHT", reason="Delivered.",
)


def test_fight_maps_to_evidence_submission():
    report = run_draft("PP-R-0001", FakeLLM(FIGHT))
    assert report.action == SUBMIT_EVIDENCE
    assert not report.blocked


def test_evidence_types_are_normalized():
    report = run_draft("PP-R-0001", FakeLLM(FIGHT))
    assert report.evidence_types == ["TRANSACTION_DETAILS"]


def test_uncovered_sentence_blocks_fight():
    draft = FIGHT.model_copy(update={
        "response_text": "The item was delivered on 2026-10-06. The buyer requested a refund on 2026-10-05."
    })
    report = run_draft("PP-R-0001", FakeLLM(draft))
    assert report.blocked
    assert report.uncovered == ["The buyer requested a refund on 2026-10-05."]


def test_accept_on_open_dispute_is_not_blocked_and_sends_no_evidence():
    accept = Draft(evidence_types=[], response_text="We accept the claim.", claims=[],
                   recommendation="ACCEPT", reason="In transit; cannot prove delivery.")
    report = run_draft("PP-R-0002", FakeLLM(accept))
    assert report.action == ACCEPT_CLAIM
    assert not report.blocked


def test_accept_on_closed_dispute_is_blocked():
    accept = Draft(evidence_types=[], response_text="We accept the claim.", claims=[],
                   recommendation="ACCEPT", reason="Closed.")
    report = run_draft("PP-R-0003", FakeLLM(accept))
    assert report.action == ACCEPT_CLAIM
    assert report.blocked


def test_escalate_goes_to_human_and_is_never_blocked_from_sending():
    escalate = Draft(evidence_types=[], response_text="Unclear.", claims=[],
                     recommendation="ESCALATE", reason="Evidence is mixed.")
    report = run_draft("PP-R-0002", FakeLLM(escalate))
    assert report.action == HUMAN_REVIEW
    assert not report.blocked
