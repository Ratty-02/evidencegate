# PayPal sandbox: what works, what doesn't, what is untested

## Works (verified against the real sandbox)

- OAuth client-credentials token request. `python -m scripts.paypal_check` prints `Token OK`.
- Listing disputes (`GET /v1/customer/disputes`). It returns successfully, with zero items.

## Blocked (external to this code)

- **Creating a sandbox dispute failed with "account not supported."** Both the sandbox UI and the API route are affected. PayPal's documentation says the API route also needs the `DISPUTE_CREATE` scope on the REST app, which must be added by PayPal (through an account manager), plus buyer consent through "Log in with PayPal." Until PayPal enables this for the sandbox app, the app has no real disputes to read or respond to.
- **Workaround to try:** create a new sandbox business and personal account pair, then send a payment and open a dispute from the new pair.

## Assumed, not yet verified

- Field names in the real dispute response: `dispute_amount`, `disputed_transactions[].seller_transaction_id`, `seller_response_due_date`. These live in `app/paypal/source.py`. When a real dispute exists, compare `fixtures/sandbox/dispute_detail.json` with them.
- Evidence type names. The gate normalizes them to uppercase, but PayPal's accepted names must come from its reason table.
- The accept-claim body (`reason`, `note`) and the reason list (`NOT_ABLE_TO_WIN` is confirmed in docs; the full list is not).
- Whether PayPal honors the `PayPal-Request-Id` header on dispute writes.
- The webhook verification request body and the event names `CUSTOMER.DISPUTE.*`.

## Known limits of this prototype

- Sentence coverage is word-based. A paraphrase can be flagged as uncovered even when it's accurate. Good drafts are sometimes blocked; this is the safe direction, but it has not been measured on real model output.
- The gate checks grounding and status, not whether the argument is right. Merit warnings are advisory.
- The evaluation uses labeled cases with errors injected by the author. It shows the gate catches those errors, not how often a real model makes them.
- The login is a single shared username and password. It is not suitable for production.
