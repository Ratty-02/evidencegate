# Project description (for the submission form)

## One line
EvidenceGate: an AI-drafted, rules-checked dispute response that merchants approve only after every claim is traced to a record.

## What it does
Merchants answer PayPal payment disputes under deadline pressure. EvidenceGate lists disputes on a case board. For each case, an AI model drafts a response in which every sentence is tied to a claim with a source record. A deterministic gate then checks:

1. **PayPal rules:** the dispute is still open, PayPal's evidence link exists, and files meet the allowed type and size.
2. **Grounding:** every claim cites a real record, and the cited value matches exactly.
3. **Coverage:** every sentence in the response is backed by a claim.
4. **Warnings:** when cited records suggest the fight is weak (for example, shipment still in transit), the merchant is warned. Warnings never block.

Blocked drafts cannot be approved. The merchant slides to approve, and each approval is stored with a request ID for audit. In real mode, approval is sent to PayPal after the gate is checked again.

## Features
- Sign-up with email verification, password reset, and sign-in throttling
- Multi-tenant workspaces: each merchant's drafts, records, and approvals are private
- Per-merchant PayPal connection, with the client secret encrypted at rest
- Merchant records by pasted CSV or uploaded file
- Case board, case pages, five-stage gate pipeline, evidence view
- Labeled evaluation harness with injected errors, plus a paraphrase measurement

## How AI is used
- **Model:** `openai/gpt-oss-120b` through Groq's API.
- **Task:** choose evidence types, draft the response as structured claims, and recommend an action (fight, accept, or escalate), returned as strict JSON.
- **Control:** the model's output is validated against a schema and then checked by ordinary code. The model never submits anything. Malformed output is rejected.

## How PayPal is used
- **Authentication:** OAuth2 client credentials, with cached tokens and retries.
- **Reads:** list and show customer disputes through the Disputes API.
- **Writes:** provide-evidence and accept-claim, with a `PayPal-Request-Id` header and retries that reuse it. Sent only after the gate passes and a person approves.
- **Webhooks:** signature verification through PayPal's verification endpoint; events are stored only after the signature checks out.
- **Status:** the sandbox connection and dispute listing are verified against PayPal's sandbox. Creating a sandbox dispute is blocked by PayPal's account setup (see `docs/sandbox_limits.md`), so the write path is tested offline against PayPal's documented request shapes.

## Tools used
- Groq API (model inference)
- PayPal REST APIs: Disputes, OAuth, webhook verification (sandbox)
- Python, FastAPI, SQLite, Jinja2, Pydantic, cryptography (Fernet)
- Postman (collection of the PayPal requests: `postman/evidencegate.postman_collection.json`)
- Render (hosting for the public demo)

## How to run it
See the Quick start and "For judges" sections of the README. The demo runs in mock mode with no PayPal credentials required.

## Limits, stated plainly
- Dispute data is mock data unless a merchant connects PayPal credentials and a dispute exists in their account.
- Sentence coverage is word-based and blocks some accurate paraphrases; the rate is measured in `evals/results/paraphrase.json`.
- The evaluation uses labeled cases the author designed. It shows the gate catches the errors listed, not how often a real model errs.
- Email delivery in demo mode shows links on screen; production uses SMTP.

## Development and declarations
- **Entry type:** solo. No team representative.
- **Originality:** built during the submission period as a new project. All code is the entrant's work, except the open-source dependencies listed in `docs/official_rules_check.md`.
- **Sponsor or administrator support:** none received.
- **AI assistance:** the entrant used an AI coding assistant during development. Product decisions, the gate design, and all testing and evaluation were directed by the entrant.
- **Third-party services:** PayPal sandbox APIs and Groq's API, used under their terms. Details are in `docs/official_rules_check.md`.
