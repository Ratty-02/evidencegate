# PayPal sandbox: what works, what doesn't, what is untested

## Works (verified against the real sandbox)

- OAuth client-credentials token request (`python -m scripts.paypal_check`).
- Listing disputes (`GET /v1/customer/disputes`). It succeeds with zero items.
- `python -m scripts.diagnose_sandbox` reports the OAuth scopes PayPal grants to the app.

## Blocked (external to this code)

- **Creating a sandbox dispute fails with "account not supported."** The sandbox web
  interface shows this, and PayPal's documentation says the API route also needs a dispute
  creation scope (DISPUTE_CREATE) granted by PayPal, plus buyer consent. Until PayPal enables
  this for the sandbox app, the app has no real disputes to read or respond to.
- **Next steps:** run `python -m scripts.diagnose_sandbox`, then send the request in
  `docs/sandbox_support_request.md`. Also try a new sandbox business and personal account pair.

## Assumed, not yet verified

- Field names in the real dispute response: `dispute_amount`, `disputed_transactions[].seller_transaction_id`,
  `seller_response_due_date` (see `app/paypal/source.py`). Compare with `fixtures/sandbox/dispute_detail.json`
  once a real dispute exists.
- Evidence type names. The gate normalizes them to uppercase; PayPal's accepted names must come from its reason table.
- The accept-claim body (`reason`, `note`). `NOT_ABLE_TO_WIN` is confirmed in the docs; the full reason list is not.
- Whether PayPal honors the `PayPal-Request-Id` header on dispute writes.
- The webhook verification request and the `CUSTOMER.DISPUTE.*` event names.

## Known limits of this prototype

- Sentence coverage is word-based, so accurate paraphrases can be flagged. This has not been measured on real model output.
- The gate checks grounding and status, not whether the argument is right. Merit warnings are advisory.
- The evaluation uses labeled cases with errors injected by the author. It does not measure real model error rates.
- Sign-in is for a single shared workspace. There is no email verification, password reset, or login rate limiting.
