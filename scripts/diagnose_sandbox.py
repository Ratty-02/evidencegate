"""Diagnose the PayPal sandbox setup and write a report for PayPal support.

Checks, in order:
  1. The app can get an access token.
  2. Which OAuth scopes PayPal granted to the app (dispute scopes in particular).
  3. The app can list disputes.

Writes fixtures/sandbox/diagnostics.json. No secrets are printed or saved.

Usage (from project root):
    python -m scripts.diagnose_sandbox
"""
import datetime
import json
from pathlib import Path

from app.paypal.client import PayPalError, RealPayPalClient

OUT = Path(__file__).resolve().parents[1] / "fixtures" / "sandbox" / "diagnostics.json"


def _save_and_print(report: dict) -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"\nSaved to {OUT}")


def main() -> None:
    client = RealPayPalClient()
    report = {
        "checked_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "environment": client.base_url,
    }

    try:
        client.access_token()
        report["token"] = "OK"
    except PayPalError as exc:
        report["token"] = f"FAILED: {exc}"
        report["summary"] = "The app cannot authenticate. Check PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET in .env."
        _save_and_print(report)
        return

    report["granted_scopes"] = client.scopes
    report["dispute_scopes"] = [s for s in client.scopes if "dispute" in s.lower()]

    try:
        listing = client.list_disputes()
        items = listing.get("items") or listing.get("disputes") or []
        report["dispute_listing"] = f"OK, {len(items)} item(s)"
    except PayPalError as exc:
        report["dispute_listing"] = f"FAILED: {exc}"

    if report["dispute_listing"].startswith("FAILED"):
        report["summary"] = ("The dispute API call failed. Include the dispute_listing message "
                             "in the PayPal support request.")
    elif not report["dispute_scopes"]:
        report["summary"] = ("Authentication works, but no dispute-related scope is granted to this app. "
                             "Ask PayPal support to enable dispute scopes for this sandbox app.")
    else:
        report["summary"] = ("Authentication and dispute listing work. "
                             "Dispute creation is still unverified; see docs/sandbox_support_request.md.")

    _save_and_print(report)


if __name__ == "__main__":
    main()
