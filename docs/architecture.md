# Architecture

```
Browser ──► FastAPI routes (app/web/routes.py)
              │  optional HTTP Basic login (app/main.py, when APP_PASSWORD is set)
              │
              ├─► Data source
              │     mock:  MockPayPalClient (fixtures/)
              │     real:  RealDisputeSource ─► RealPayPalClient (OAuth, retries)
              │
              ├─► Draft pipeline (app/ai/pipeline.py)
              │     Groq model returns JSON ─► Draft schema (Pydantic)
              │     check_draft: rules, grounding, coverage, merit warnings
              │
              ├─► Submission (app/services/submission.py)
              │     re-runs the gate, then provide-evidence or accept-claim
              │
              └─► SQLite (app/db.py)
                    drafts, approvals (audit), merchant records, webhook events

PayPal ──webhook──► /webhooks/paypal ─► signature check ─► events table
```

## Key decisions

- **The gate runs on every read and every write.** Drafts are stored as the model's output, and checks re-run on load, so a rule change applies immediately.
- **Submission re-checks the gate.** A blocked draft cannot reach PayPal, even if a caller skips the UI.
- **One data interface for mock and real data.** Both sources expose list, get, and records, so the rest of the app doesn't change.
- **Merchant records are separate from PayPal data.** PayPal doesn't provide delivery proof, so the merchant supplies it, and the app labels it as merchant-provided.
- **Idempotency.** Writes send a PayPal-Request-Id header, and retries reuse it.

## Modules

| Path | Purpose |
|---|---|
| `app/rules/paypal_evidence.py` | Status, evidence link, file, and size rules |
| `app/rules/grounding.py` | Claim-to-record matching and sentence coverage |
| `app/ai/` | Groq client, output schema, prompt, pipeline |
| `app/paypal/` | Auth, retries, read and write endpoints, webhook verification, data source |
| `app/records.py` | CSV parsing for merchant records |
| `app/services/submission.py` | Gate-checked submission |
| `app/db.py` | SQLite storage |
| `app/web/` | Routes, templates, styles, and motion |
| `evals/` | Labeled cases with injected errors, offline and live runs |
