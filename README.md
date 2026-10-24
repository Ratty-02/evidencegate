# EvidenceGate

**Gate the Guesswork.** EvidenceGate helps merchants answer PayPal payment disputes. An AI model drafts the response, and a deterministic gate checks every claim against a record before anyone can approve it. A person approves each submission.

## What it does

1. Lists disputes (mock data by default; the real PayPal sandbox when `PAYPAL_MOCK=false`).
2. Lets the merchant paste their own tracking records as CSV, since PayPal does not provide delivery proof.
3. Generates a draft response in which each sentence is tied to a claim.
4. Runs the gate: PayPal's status and file rules, claim-to-record grounding, and sentence coverage.
5. Shows warnings when cited records suggest fighting may be weak.
6. Requires a slide-to-approve action. Blocked drafts cannot be approved.
7. Records every approval with a request ID. In real mode, the approval is sent to PayPal.

## Quick start (Windows PowerShell)

```powershell
cd evidencegate
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

Edit `.env`:
- `SESSION_SECRET`: a long random string (run `python -c "import secrets; print(secrets.token_urlsafe(48))"`)
- `LLM_API_KEY`: your Groq key
- `PAYPAL_MOCK=true` for the demo

Start the app:

```powershell
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000, create an account, and sign in.

## Tests and evaluation

```powershell
python -m pytest -q          # unit, integration, and auth tests (offline)
python -m evals.run_eval     # gate evaluation on labeled cases (offline)
python -m evals.run_eval --live   # one real model run per fixture dispute (uses LLM_API_KEY)
python -m scripts.paypal_check    # checks the PayPal sandbox connection (uses PayPal credentials)
```

## Configuration

| Variable | Purpose |
|---|---|
| `PAYPAL_MOCK` | `true` uses fixture disputes; `false` uses the PayPal API |
| `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET`, `PAYPAL_ENV` | PayPal REST app credentials |
| `PAYPAL_WEBHOOK_ID` | Needed to verify webhook signatures |
| `SESSION_SECRET` | Signs session cookies. Required in production |
| `SESSION_MAX_AGE_DAYS` | How long a sign-in lasts (default 7) |
| `COOKIE_SECURE` | `true` when served over HTTPS |
| `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL` | Groq model settings |
| `DATABASE_URL` | SQLite file (default `sqlite:///./evidencegate.db`) |

## How AI is used

- **Drafting:** a Groq-hosted open model returns strict JSON (evidence types, response text, claims with record citations, a recommendation, and a reason). Output that fails schema validation is rejected.
- **Checking:** the model's output is not trusted. The gate checks it with ordinary code.
- The model never submits anything.

## How PayPal is used

- OAuth2 client-credentials authentication with cached tokens and retries (`app/paypal/client.py`).
- Reads: list and show customer disputes.
- Writes: provide evidence and accept claim, with a `PayPal-Request-Id` for idempotency. Only sent after the gate passes and a person approves.
- Webhook signature verification (`/webhooks/paypal`). Events are stored only after PayPal confirms the signature.

**Status:** reads work against the sandbox. No sandbox dispute exists yet, because the sandbox account returned "account not supported" when creating one. The write path is tested offline against PayPal's documented request shapes. See `docs/sandbox_limits.md`.

## Security

- Accounts require sign-up with a password of at least 8 characters.
- Passwords are stored as PBKDF2-SHA256 hashes with per-password salts.
- Sessions use signed, expiring, HttpOnly cookies.
- Case pages, records, drafts, and approvals require sign-in.
- The PayPal webhook is public but accepts only events with a valid PayPal signature.

Known gaps: no email verification, password reset, or login rate limiting. All signed-in users share one workspace, so this is not a multi-tenant product.

## Deploying (Render)

1. Create a Web Service from this repository.
2. Build command: `pip install -r requirements.txt`
3. Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. Set environment variables: `SESSION_SECRET`, `COOKIE_SECURE=true`, `PAYPAL_MOCK=true`, `LLM_API_KEY`, and the LLM settings.
5. Open the service URL, create an account, and check the case board.

Render's free tier sleeps when idle; open the link a minute before a demo.

## Limitations

- Sentence coverage is word-based, so accurate paraphrases can be flagged. This is the safe direction, but good drafts are sometimes blocked.
- The gate checks grounding and status, not whether fighting is the right choice.
- The evaluation uses labeled cases with errors injected by the author. It does not measure real model error rates.

## License

MIT. See `LICENSE`.

## Workspaces (multi-tenant)

Each account has its own workspace. Drafts, approvals, and merchant records are stored per
user, and one merchant cannot see another's. Tests in `tests/test_tenancy.py` check this.

Current limit: all accounts share the same PayPal app credentials (set in `.env`). A
production version would store each merchant's own PayPal credentials, encrypted at rest.

**Upgrading from the single-workspace version:** delete `evidencegate.db` once. This clears
local drafts, approvals, and records. The app refuses to start on the old format and tells you so.
