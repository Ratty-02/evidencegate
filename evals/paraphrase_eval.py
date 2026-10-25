"""Measure false blocks from sentence coverage on accurate paraphrases.

Every case is a correct statement: its claim matches a mock record. The only
difference between a control and a paraphrase is the wording of the response
sentence. Controls repeat the claim exactly. Paraphrases reword it. A blocked
paraphrase is a false block: the gate stopped a correct statement.

Runs offline with no model call. Results are written to evals/results/paraphrase.json.

Usage (from project root):
    python -m evals.paraphrase_eval
"""
import json
from pathlib import Path

from app.ai.pipeline import check_draft
from app.ai.schemas import Draft, DraftClaim

DISPUTE = "PP-R-0001"
RESULTS = Path(__file__).parent / "results" / "paraphrase.json"

# (kind, response sentence, claim statement, record_id, field, value)
CASES = [
    ("control", "The item was delivered on 2026-10-06.",
     "The item was delivered on 2026-10-06.", "TRK-1001", "delivered_on", "2026-10-06"),
    ("paraphrase", "The parcel reached the buyer on 2026-10-06.",
     "The item was delivered on 2026-10-06.", "TRK-1001", "delivered_on", "2026-10-06"),
    ("paraphrase", "Our tracking shows the order was delivered on 2026-10-06.",
     "Delivered on 2026-10-06.", "TRK-1001", "delivered_on", "2026-10-06"),
    ("control", "The transaction amount was $49.00 USD.",
     "The transaction amount was $49.00 USD.", "TXN-1001", "amount", "49.00"),
    ("paraphrase", "The buyer paid 49.00 USD for the order.",
     "The transaction amount was $49.00 USD.", "TXN-1001", "amount", "49.00"),
    ("paraphrase", "The customer was charged 49.00 USD.",
     "The transaction amount was $49.00 USD.", "TXN-1001", "amount", "49.00"),
    ("control", "The order was placed on 2026-10-01.",
     "The order was placed on 2026-10-01.", "TXN-1001", "order_date", "2026-10-01"),
    ("paraphrase", "The purchase was made on 2026-10-01.",
     "The order was placed on 2026-10-01.", "TXN-1001", "order_date", "2026-10-01"),
    ("paraphrase", "The buyer ordered the item on 2026-10-01.",
     "The order was placed on 2026-10-01.", "TXN-1001", "order_date", "2026-10-01"),
    ("control", "The item was shipped via FEDEX with tracking number 122533485.",
     "The item was shipped via FEDEX with tracking number 122533485.", "TRK-1001", "carrier", "FEDEX"),
    ("paraphrase", "FEDEX carried the parcel under tracking number 122533485.",
     "The item was shipped via FEDEX with tracking number 122533485.", "TRK-1001", "carrier", "FEDEX"),
    ("paraphrase", "The package went out with FEDEX, tracking 122533485.",
     "The item was shipped via FEDEX with tracking number 122533485.", "TRK-1001", "carrier", "FEDEX"),
]


def _draft(response: str, statement: str, record_id: str, field: str, value: str) -> Draft:
    return Draft(
        evidence_types=["PROOF_OF_DELIVERY"],
        response_text=response,
        claims=[DraftClaim(statement=statement, record_id=record_id, field=field, value=value)],
        recommendation="FIGHT",
        reason="Paraphrase measurement case.",
    )


def run() -> dict:
    details = []
    for kind, response, statement, record_id, field, value in CASES:
        report = check_draft(DISPUTE, _draft(response, statement, record_id, field, value), merchant_records={})
        claims_ok = all(r.status == "SUPPORTED" for r in report.claims)
        details.append({
            "kind": kind,
            "response": response,
            "blocked": report.blocked,
            "claims_supported": claims_ok,
            "uncovered": report.uncovered,
            # Blocked although every claim is supported: the block came from wording alone.
            "false_block": kind == "paraphrase" and report.blocked and claims_ok,
        })

    controls = [d for d in details if d["kind"] == "control"]
    paraphrases = [d for d in details if d["kind"] == "paraphrase"]
    summary = {
        "controls_passed": sum(not d["blocked"] for d in controls),
        "controls_total": len(controls),
        "paraphrases_blocked": sum(d["false_block"] for d in paraphrases),
        "paraphrases_total": len(paraphrases),
        "false_block_rate": round(sum(d["false_block"] for d in paraphrases) / len(paraphrases), 3),
    }
    payload = {"summary": summary, "cases": details}
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    RESULTS.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def main() -> None:
    payload = run()
    s = payload["summary"]
    print(f"Controls passed:          {s['controls_passed']}/{s['controls_total']}")
    print(f"Paraphrases wrongly blocked: {s['paraphrases_blocked']}/{s['paraphrases_total']} "
          f"({s['false_block_rate'] * 100:.0f}%)")
    print("\nWrongly blocked paraphrases:")
    for d in payload["cases"]:
        if d["false_block"]:
            print(f"  - {d['response']}")
    print(f"\nSaved to {RESULTS}")


if __name__ == "__main__":
    main()
