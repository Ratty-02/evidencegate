"""Send an approved report to PayPal.

The gate is checked again here, not only in the UI, so a blocked draft can
never reach PayPal even if a caller skips the approve button.
"""
from app.ai.pipeline import ACCEPT_CLAIM, HUMAN_REVIEW, SUBMIT_EVIDENCE, Report

# PayPal's accept-claim reasons include NOT_ABLE_TO_WIN and COMPANY_POLICY.
# Confirm the full list in PayPal's dispute reasons reference.
DEFAULT_ACCEPT_REASON = "NOT_ABLE_TO_WIN"


class SubmissionRefused(Exception):
    pass


def _has_evidence_link(dispute: dict) -> bool:
    return any(link.get("rel") == "provide-evidence" for link in dispute.get("links", []))


def build_evidences(report: Report) -> list[dict]:
    return [
        {"evidence_type": t, "notes": report.draft.response_text}
        for t in report.evidence_types
    ]


def submit_report(report: Report, dispute: dict, client, request_id: str) -> dict:
    if report.blocked:
        raise SubmissionRefused("the gate blocked this draft")
    if report.action == HUMAN_REVIEW:
        raise SubmissionRefused("this case needs a human decision")
    if report.action == SUBMIT_EVIDENCE:
        if not _has_evidence_link(dispute):
            raise SubmissionRefused("PayPal did not offer an evidence link for this dispute")
        return client.provide_evidence(report.dispute_id, build_evidences(report), request_id)
    if report.action == ACCEPT_CLAIM:
        return client.accept_claim(
            report.dispute_id,
            reason=DEFAULT_ACCEPT_REASON,
            note=report.draft.reason,
            request_id=request_id,
        )
    raise SubmissionRefused(f"unknown action {report.action!r}")
