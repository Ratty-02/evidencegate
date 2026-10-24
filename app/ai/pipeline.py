"""Draft pipeline: ask the model for a draft, then run deterministic checks.

Recommendation -> action:
  FIGHT    -> SUBMIT_EVIDENCE  (rules, claim grounding, sentence coverage)
  ACCEPT   -> ACCEPT_CLAIM     (status check only; no evidence is sent)
  ESCALATE -> HUMAN_REVIEW     (nothing is sent; a person decides)

Records come from PayPal (when available) plus merchant-supplied records.
Merit warnings do not block; they tell the merchant when cited records
suggest the fight may be weak.
"""
import json
from dataclasses import dataclass, field
from pathlib import Path

from app import db
from app.ai.schemas import Draft
from app.paypal.mock_client import MockPayPalClient
from app.rules.grounding import (
    Claim,
    ClaimResult,
    check_claims,
    submission_blocked,
    uncovered_sentences,
)
from app.rules.paypal_evidence import (
    RulesResult,
    check_status,
    check_submission,
    normalize_evidence_type,
)

PROMPT = (Path(__file__).parent / "prompts" / "draft.txt").read_text(encoding="utf-8")

SUBMIT_EVIDENCE = "SUBMIT_EVIDENCE"
ACCEPT_CLAIM = "ACCEPT_CLAIM"
HUMAN_REVIEW = "HUMAN_REVIEW"
ACTION_FOR = {"FIGHT": SUBMIT_EVIDENCE, "ACCEPT": ACCEPT_CLAIM, "ESCALATE": HUMAN_REVIEW}
WARN_STATUSES = {"IN_TRANSIT", "PENDING", "LOST", "RETURNED"}


@dataclass
class Report:
    dispute_id: str
    draft: Draft
    action: str
    evidence_types: list[str]
    rules: RulesResult
    claims: list[ClaimResult]
    uncovered: list[str]
    blocked: bool
    warnings: list[str] = field(default_factory=list)


def build_user_message(dispute: dict, records: dict[str, dict]) -> str:
    return json.dumps({"dispute": dispute, "records": records}, indent=2)


def load_records(dispute_id: str, paypal, merchant_records: dict | None = None):
    """Return (dispute, records) where records merges PayPal and merchant data."""
    dispute = paypal.get_dispute(dispute_id)
    base = paypal.get_records(dispute)
    extra = db.get_records(dispute_id) if merchant_records is None else merchant_records
    merged = {rid: dict(fields) for rid, fields in base.items()}
    for rid, fields in extra.items():
        merged.setdefault(rid, {}).update(fields)
    return dispute, merged


def merit_warnings(action: str, claims: list[Claim], records: dict[str, dict]) -> list[str]:
    if action != SUBMIT_EVIDENCE:
        return []
    warnings = []
    for claim in claims:
        if claim.record_id and claim.record_id in records:
            status = str(records[claim.record_id].get("status", "")).upper()
            if status in WARN_STATUSES:
                warnings.append(
                    f"{claim.record_id} shows status {status}. "
                    "Check whether fighting is still the right call."
                )
    return sorted(set(warnings))


def check_draft(dispute_id: str, draft: Draft, paypal=None, merchant_records: dict | None = None) -> Report:
    """Run every deterministic check on a draft. No model call."""
    paypal = paypal or MockPayPalClient()
    dispute, records = load_records(dispute_id, paypal, merchant_records)

    action = ACTION_FOR[draft.recommendation]
    evidence_types = [normalize_evidence_type(t) for t in draft.evidence_types]
    claims = [Claim(c.statement, c.record_id, c.field, c.value) for c in draft.claims]

    claim_results: list[ClaimResult] = []
    uncovered: list[str] = []
    if action == SUBMIT_EVIDENCE:
        rules = check_submission(dispute, evidence_types, files=[])
        claim_results = check_claims(claims, records)
        uncovered = uncovered_sentences(draft.response_text, claims)
        blocked = (not rules.ok) or submission_blocked(claim_results) or bool(uncovered)
    elif action == ACCEPT_CLAIM:
        rules = check_status(dispute)
        blocked = not rules.ok
    else:  # HUMAN_REVIEW: nothing is sent
        rules = check_status(dispute)
        blocked = False

    return Report(
        dispute_id, draft, action, evidence_types, rules,
        claim_results, uncovered, blocked,
        merit_warnings(action, claims, records),
    )


def run_draft(dispute_id: str, llm, paypal=None, merchant_records: dict | None = None) -> Report:
    """Ask the model for a draft, then check it."""
    paypal = paypal or MockPayPalClient()
    dispute, records = load_records(dispute_id, paypal, merchant_records)
    draft = llm.draft(PROMPT, build_user_message(dispute, records))
    return check_draft(dispute_id, draft, paypal, merchant_records)


def status_line(report: Report) -> str:
    if report.action == HUMAN_REVIEW:
        return "No submission. A person needs to decide this one."
    if report.blocked:
        return "SUBMISSION BLOCKED"
    if report.action == SUBMIT_EVIDENCE:
        return "Ready for merchant approval: submit evidence"
    return "Ready for merchant approval: accept claim"


def format_report(report: Report) -> str:
    d = report.draft
    lines = [
        f"Dispute: {report.dispute_id}",
        f"Recommendation: {d.recommendation}",
        f"Action: {report.action}",
        f"Reason: {d.reason}",
        f"Evidence types: {', '.join(report.evidence_types) or 'none'}",
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
    if report.uncovered:
        lines += ["", "Sentences with no source claim:"]
        lines += [f"  {s}" for s in report.uncovered]
    if report.warnings:
        lines += ["", "Warnings:"] + [f"  {w}" for w in report.warnings]
    lines += ["", "Rules:"]
    if report.rules.ok:
        lines.append("  all checks passed")
    for issue in report.rules.issues:
        lines.append(f"  [{issue.code}] {issue.message}")
    lines += ["", status_line(report)]
    return "\n".join(lines)
