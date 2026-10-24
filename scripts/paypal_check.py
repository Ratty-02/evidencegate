"""Check the PayPal sandbox connection.

Gets an access token, lists disputes, and saves the raw responses to
fixtures/sandbox/ so the mock fixtures can be checked against real shapes.
The token and secret are never printed.

Usage (from project root):
    python -m scripts.paypal_check
"""
import json
from pathlib import Path

from app.paypal.client import PayPalError, RealPayPalClient

OUT = Path(__file__).resolve().parents[1] / "fixtures" / "sandbox"


def main() -> None:
    client = RealPayPalClient()
    try:
        client.access_token()
    except PayPalError as exc:
        print(f"FAILED: {exc}")
        return
    print("Token OK (value not shown).")

    OUT.mkdir(parents=True, exist_ok=True)
    listing = client.list_disputes()
    (OUT / "disputes_list.json").write_text(json.dumps(listing, indent=2), encoding="utf-8")

    items = listing.get("items") or listing.get("disputes") or []
    print(f"Sandbox disputes found: {len(items)}")
    for item in items[:5]:
        print(f"  - {item.get('dispute_id')}  status={item.get('status')}  reason={item.get('reason')}")

    if items:
        dispute_id = items[0]["dispute_id"]
        detail = client.get_dispute(dispute_id)
        (OUT / "dispute_detail.json").write_text(json.dumps(detail, indent=2), encoding="utf-8")
        print(f"Saved full detail for {dispute_id}")

    print(f"Raw responses saved to {OUT}")


if __name__ == "__main__":
    main()
