"""Evaluate the gate on labeled cases with injected errors.

Offline (default): no model calls. Each case is a hand-written draft for a
fixture dispute. Clean drafts must pass. Drafts with one injected error must
be blocked. Closed or unclear cases must be routed correctly.

What this measures: whether the gate catches the error types listed below.
It does NOT measure how often a real model makes these errors. Use --live
for that, which runs the model once on each fixture dispute.

Known limit: the gate checks grounding and status, not whether the merchant's
argument is right. A FIGHT on a shipment that is still in transit passes if
its claims match the records.

Usage (from project root):
    python -m evals.run_eval            # offline gate evaluation
    python -m evals.run_eval --live     # real model on each fixture dispute
"""
import argparse
import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from app.ai.pipeline import ACCEPT_CLAIM, HUMAN_REVIEW, SUBMIT_EVIDENCE, check_draft, run_draft
from app.ai.schemas import Draft, DraftClaim

RESULTS_DIR = Path(__file__).parent / "results"

# (statement, record_id, field, value). Each statement is also the sentence in the response.
ROWS_0001 = [
    ("The transaction amount was $49.00 USD.", "TXN-1001", "amount", "49.00"),
    ("The order was placed on 2026-10-01.", "TXN-1001", "order_date", "2026-10-01"),
    ("The item was shipped via FEDEX with tracking number 122533485.", "TRK-1001", "carrier", "FEDEX"),
    ("The item was delivered on 2026-10-06.", "TRK-1001", "delivered_on", "2026-10-06"),
]
ROWS_0002_AMOUNT = [
    ("The transaction amount was $120.00 USD.", "TXN-1002", "amount", "120.00"),
    ("The shipment is with UPS under tracking number 1Z999AA10123456784.", "TRK-1002", "carrier", "UPS"),
]
ROWS_0003 = [
    ("The transaction amount was $35.00 USD.", "TXN-1003", "amount", "35.00"),
]


def build(rows, recommendation, evidence=(), extra_sentences=(), reason="eval case"):
    claims = [DraftClaim(statement=s, record_id=r, field=f, value=v) for s, r, f, v in rows]
    text = " ".join([s for s, *_ in rows] + list(extra_sentences))
    return Draft(evidence_types=list(evidence), response_text=text, claims=claims,
                 recommendation=recommendation, reason=reason)


def with_value(rows, i, value):
    s, r, f, _ = rows[i]
    return rows[:i] + [(s, r, f, value)] + rows[i + 1:]


def with_record(rows, i, record_id):
    s, _, f, v = rows[i]
    return rows[:i] + [(s, record_id, f, v)] + rows[i + 1:]


def with_field(rows, i, field_name):
    s, r, _, v = rows[i]
    return rows[:i] + [(s, r, field_name, v)] + rows[i + 1:]


def without(rows, i):
    return rows[:i] + rows[i + 1:]


def drop_claim(draft, index):
    """Keep the response sentence but remove its claim."""
    kept = [c for i, c in enumerate(draft.claims) if i != index]
    return draft.model_copy(update={"claims": kept})


@dataclass
class Case:
    case_id: str
    dispute_id: str
    kind: str            # "clean" | "injected" | "routing"
    error: str | None    # name of the injected error, if any
    draft: Draft
    expect_blocked: bool
    expect_action: str | None = None


def build_cases() -> list[Case]:
    cases: list[Case] = []

    def add(case_id, dispute_id, kind, draft, expect_blocked, expect_action=None, error=None):
        cases.append(Case(case_id, dispute_id, kind, error, draft, expect_blocked, expect_action))

    # PP-R-0001: open, delivered. Clean FIGHT plus six injected errors.
    evid = ["PROOF_OF_DELIVERY"]
    add("0001-clean", "PP-R-0001", "clean", build(ROWS_0001, "FIGHT", evid),
        False, SUBMIT_EVIDENCE)
    add("0001-wrong-amount", "PP-R-0001", "injected",
        build(with_value(ROWS_0001, 0, "45.00"), "FIGHT", evid), True, error="wrong_value")
    add("0001-wrong-delivery-date", "PP-R-0001", "injected",
        build(with_value(ROWS_0001, 3, "2026-10-03"), "FIGHT", evid), True, error="wrong_value")
    add("0001-fabricated-record", "PP-R-0001", "injected",
        build(with_record(ROWS_0001, 3, "TRK-9999"), "FIGHT", evid), True, error="fabricated_record")
    add("0001-unknown-field", "PP-R-0001", "injected",
        build(with_field(ROWS_0001, 1, "signed_at"), "FIGHT", evid), True, error="unknown_field")
    add("0001-uncovered-sentence", "PP-R-0001", "injected",
        build(ROWS_0001, "FIGHT", evid, extra_sentences=["The buyer confirmed receipt in writing."]),
        True, error="uncovered_sentence")
    add("0001-dropped-claim", "PP-R-0001", "injected",
        drop_claim(build(ROWS_0001, "FIGHT", evid), 1), True, error="uncovered_sentence")

    # PP-R-0002: open, in transit. Clean ACCEPT, overstated FIGHT, wrong amount, escalate.
    add("0002-clean-accept", "PP-R-0002", "clean",
        Draft(evidence_types=[], response_text="We accept this claim.", claims=[],
              recommendation="ACCEPT", reason="Parcel is still in transit."),
        False, ACCEPT_CLAIM)
    add("0002-overstated-delivery", "PP-R-0002", "injected",
        Draft(evidence_types=["PROOF_OF_DELIVERY"],
              response_text="The shipment was delivered.",
              claims=[DraftClaim(statement="The shipment was delivered.", record_id="TRK-1002",
                                 field="status", value="DELIVERED")],
              recommendation="FIGHT", reason="Claims delivery."),
        True, error="overstated_status")
    add("0002-wrong-amount", "PP-R-0002", "injected",
        build(with_value(ROWS_0002_AMOUNT, 0, "210.00"), "FIGHT", evid), True, error="wrong_value")
    add("0002-escalate", "PP-R-0002", "routing",
        Draft(evidence_types=[], response_text="The evidence is mixed.", claims=[],
              recommendation="ESCALATE", reason="Unclear."),
        False, HUMAN_REVIEW)

    # PP-R-0003: resolved. Any submission must be blocked.
    add("0003-closed-fight", "PP-R-0003", "injected", build(ROWS_0003, "FIGHT", evid),
        True, error="closed_dispute")
    add("0003-closed-accept", "PP-R-0003", "injected",
        Draft(evidence_types=[], response_text="We accept this claim.", claims=[],
              recommendation="ACCEPT", reason="Closed."),
        True, error="closed_dispute")

    return cases


@dataclass
class CaseResult:
    case: Case
    blocked: bool
    action: str
    issues: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        ok = self.blocked == self.case.expect_blocked
        if self.case.expect_action is not None:
            ok = ok and self.action == self.case.expect_action
        return ok


def evaluate(cases: list[Case]) -> tuple[list[CaseResult], dict]:
    results = []
    for c in cases:
        report = check_draft(c.dispute_id, c.draft)
        issues = [i.code for i in report.rules.issues]
        issues += [r.status for r in report.claims if r.status != "SUPPORTED"]
        if report.uncovered:
            issues.append("UNCOVERED_SENTENCE")
        results.append(CaseResult(c, report.blocked, report.action, issues))

    injected = [r for r in results if r.case.kind == "injected"]
    clean = [r for r in results if r.case.kind == "clean"]
    routing = [r for r in results if r.case.kind == "routing"]
    by_error: dict[str, dict] = {}
    for r in injected:
        bucket = by_error.setdefault(r.case.error, {"total": 0, "caught": 0})
        bucket["total"] += 1
        bucket["caught"] += int(r.blocked)

    summary = {
        "injected_total": len(injected),
        "injected_caught": sum(r.blocked for r in injected),
        "clean_total": len(clean),
        "clean_passed": sum(not r.blocked and r.action == r.case.expect_action for r in clean),
        "routing_total": len(routing),
        "routing_correct": sum(r.action == HUMAN_REVIEW and not r.blocked for r in routing),
        "by_error": by_error,
        "all_cases_passed": all(r.passed for r in results),
    }
    return results, summary


def print_offline(results, summary):
    print(f"{'CASE':<28}{'EXPECT':<10}{'GOT':<10}{'RESULT':<8}ISSUES")
    for r in results:
        expect = "blocked" if r.case.expect_blocked else "pass"
        got = "blocked" if r.blocked else "pass"
        status = "PASS" if r.passed else "FAIL"
        print(f"{r.case.case_id:<28}{expect:<10}{got:<10}{status:<8}{', '.join(r.issues)}")
    print()
    s = summary
    print(f"Injected errors caught:  {s['injected_caught']}/{s['injected_total']}")
    print(f"Clean drafts passed:     {s['clean_passed']}/{s['clean_total']}")
    print(f"Routing correct:         {s['routing_correct']}/{s['routing_total']}")
    print("\nBy error type:")
    for name, b in s["by_error"].items():
        print(f"  {name:<22}{b['caught']}/{b['total']}")
    print(f"\nAll cases as expected: {s['all_cases_passed']}")
    print("Note: this measures the gate on the errors injected here, not real model error rates.")


def run_live() -> list[dict]:
    from app.ai.llm import GroqClient
    from app.paypal.mock_client import MockPayPalClient

    llm = GroqClient()
    client = MockPayPalClient()
    out = []
    for d in client.list_disputes():
        entry = {"dispute_id": d["id"], "status": d["status"]}
        try:
            report = run_draft(d["id"], llm=llm, paypal=client)
            entry.update({
                "recommendation": report.draft.recommendation,
                "action": report.action,
                "blocked": report.blocked,
                "claims_supported": sum(r.status == "SUPPORTED" for r in report.claims),
                "claims_total": len(report.claims),
                "uncovered_sentences": len(report.uncovered),
                "issues": [i.code for i in report.rules.issues],
            })
        except Exception as exc:  # record the failure, keep going
            entry["error"] = f"{type(exc).__name__}: {exc}"
        out.append(entry)
        time.sleep(3)  # stay within free-tier rate limits
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="run the real model on fixture disputes")
    args = parser.parse_args()
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    if args.live:
        rows = run_live()
        (RESULTS_DIR / "live.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
        for r in rows:
            print(json.dumps(r))
        blocked = sum(1 for r in rows if r.get("blocked"))
        print(f"\nModel drafts blocked by the gate: {blocked}/{len(rows)}")
        print(f"Saved to {RESULTS_DIR / 'live.json'}")
        return

    results, summary = evaluate(build_cases())
    print_offline(results, summary)
    payload = {
        "summary": summary,
        "cases": [{"id": r.case.case_id, "kind": r.case.kind, "error": r.case.error,
                   "expected_blocked": r.case.expect_blocked, "blocked": r.blocked,
                   "action": r.action, "passed": r.passed, "issues": r.issues} for r in results],
    }
    (RESULTS_DIR / "offline.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\nSaved to {RESULTS_DIR / 'offline.json'}")


if __name__ == "__main__":
    main()
