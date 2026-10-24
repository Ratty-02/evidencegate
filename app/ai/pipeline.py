"""Draft pipeline: load a dispute, ask the model for a draft, then run the
deterministic checks on the result before anything can be submitted.
"""
import json
from dataclasses import dataclass
from pathlib import Path

from app.ai.llm import GroqClient
from app.ai.schemas import Draft
from app.paypal.mock_client import MockPayPalClient
from app.rules.grounding import Claim, ClaimResult, check_claims, submission_blocked
from app.rules.paypal_evidence import RulesResult, check_submission

PROMPT = (Path(__file__).parent / "prompts" / "draft.txt").read_text(encoding="utf-8")


@dataclass
class Report:
    dispute_id: str
    draft: Draft
    rules: RulesResult
    claims: list[ClaimResult]
    blocked: bool


def build_user_message(dispute: dict, records: dict[str, dict]) -> str:
    return json.dumps({"dispute": dispute, "records": records}, indent=2)


def run_draft(dispute_id: str, llm, paypal=None) -> Report:
    paypal = paypal or MockPayPalClient()
    dispute = paypal.get_dispute(dispute_id)
    records = paypal.get_records(dispute)

    draft = llm.draft(PROMPT, build_user_message(dispute, records))

    rules = check_submission(dispute, draft.evidence_types, files=[])
    claim_results = check_claims(
        [Claim(c.statement, c.record_id, c.field, c.value) for c in draft.claims],
        records,
    )
    blocked = (not rules.ok) or submission_blocked(claim_results)
    return Report(dispute_id, draft, rules, claim_results, blocked)


def format_report(report: Report) -> str:
    d = report.draft
    lines = [
        f"Dispute: {report.dispute_id}",
        f"Recommendation: {d.recommendation}",
        f"Reason: {d.reason}",
        f"Evidence types: {', '.join(d.evidence_types) or 'none'}",
        "",
        "Response:",
        f"  {d.response_text}",
        "",
        "Claims:",
    ]
    for r in report.claims:
        lines.append(f"  [{r.status}] {r.claim.statement} ({r.reason})")
    if not report.claims:
        lines.append("  (none)")
    lines.append("")
    lines.append("Rules:")
    if report.rules.ok:
        lines.append("  all checks passed")
    for issue in report.rules.issues:
        lines.append(f"  [{issue.code}] {issue.message}")
    lines.append("")
    lines.append("SUBMISSION BLOCKED" if report.blocked else "Ready for merchant approval")
    return "\n".join(lines)
