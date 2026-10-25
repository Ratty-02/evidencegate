"""Web routes.

Protected (signed-in, verified): case board, case pages, records, drafts,
approval, PayPal settings. Every database call uses the signed-in user's id.

Public: home and health, plus the PayPal webhook (checked by signature).
"""
import json
import uuid
from datetime import date
from decimal import Decimal
from pathlib import Path
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from app import config, db
from app.ai.llm import GroqClient, LLMOutputError
from app.ai.pipeline import HUMAN_REVIEW, Report, check_draft, run_draft
from app.paypal.client import PayPalError, RealPayPalClient
from app.paypal.mock_client import DisputeNotFound, MockPayPalClient
from app.paypal.source import RealDisputeSource
from app.records import parse_records_csv
from app.rules.paypal_evidence import ACTIONABLE_STATUS
from app.secrets_box import KeyMissing
from app.services import credentials
from app.services.submission import SubmissionRefused, submit_report
from app.web.deps import current_user, optional_user
from app.web.templating import TEMPLATES

ROOT = Path(__file__).resolve().parents[2]
OFFLINE_RESULTS = ROOT / "evals" / "results" / "offline.json"
MAX_UPLOAD_BYTES = 200_000
SAMPLE_RECORDS = "record_id,field,value\nTRK-1001,status,DELIVERED\nTRK-1001,delivered_on,2026-10-06\n"

router = APIRouter(dependencies=[Depends(current_user)])
public_router = APIRouter(dependencies=[Depends(optional_user)])

_mock_source = MockPayPalClient()


def _client_for(creds: dict) -> RealPayPalClient:
    return RealPayPalClient(client_id=creds["client_id"], client_secret=creds["client_secret"], env=creds["env"])


def get_paypal(user=Depends(current_user)):
    """A merchant's own PayPal app if connected; otherwise demo data or the server default."""
    try:
        creds = credentials.load(user["id"])
    except KeyMissing as exc:
        raise HTTPException(503, str(exc))
    if creds:
        return RealDisputeSource(_client_for(creds))
    return _mock_source if config.PAYPAL_MOCK else RealDisputeSource(RealPayPalClient())


def get_llm() -> GroqClient:
    return GroqClient()


def get_submitter(user=Depends(current_user)):
    """None means demo mode: the decision is recorded but not sent."""
    try:
        creds = credentials.load(user["id"])
    except KeyMissing as exc:
        raise HTTPException(503, str(exc))
    if creds:
        return _client_for(creds)
    return None if config.PAYPAL_MOCK else RealPayPalClient()


def get_verifier():
    if config.PAYPAL_MOCK:
        raise HTTPException(503, "webhook verification needs PAYPAL_MOCK=false and PayPal credentials")
    return RealPayPalClient()


def current_report(user_id: int, dispute_id: str, paypal) -> Report | None:
    draft = db.get_draft(user_id, dispute_id)
    if draft is None:
        return None
    return check_draft(dispute_id, draft, paypal, db.get_records(user_id, dispute_id))


def days_left(deadline: str) -> int:
    return (date.fromisoformat(deadline) - date.today()).days


def decorate(d: dict, report: Report | None, approval: dict | None) -> dict:
    """Display fields. The deadline is optional because PayPal's field may be absent."""
    is_open = d["status"] == ACTIONABLE_STATUS
    days = days_left(d["deadline"]) if d.get("deadline") else None

    if approval:
        state = "approved"
    elif report is None:
        state = "no-draft"
    elif report.blocked:
        state = "blocked"
    elif report.action == HUMAN_REVIEW:
        state = "review"
    else:
        state = "ready"

    if not is_open:
        tone, pill, ring, pct, badge_num, badge_label = "muted", "Closed", "–", 0, "–", "closed"
    elif days is None:
        tone, pill, ring, pct, badge_num, badge_label = "muted", "No deadline", "–", 0, "–", "no deadline"
    elif days < 0:
        tone, pill, ring, pct, badge_num, badge_label = "red", "Passed", "0", 0, "0", "passed"
    else:
        tone = "red" if days <= 3 else "amber" if days <= 7 else "green"
        pill, ring, pct = f"{days} days", str(days), min(days * 100 // 14, 100)
        badge_num, badge_label = str(days), "days left"

    return {
        **d,
        "is_open": is_open,
        "days_left": days,
        "deadline_tone": tone,
        "pill_text": pill,
        "ring_text": ring,
        "pct": pct,
        "badge_num": badge_num,
        "badge_label": badge_label,
        "state": state,
        "approved_action": approval["action"] if approval else None,
        "amount_value": Decimal(d["amount"]),
    }


def eval_summary() -> dict | None:
    if not OFFLINE_RESULTS.exists():
        return None
    return json.loads(OFFLINE_RESULTS.read_text(encoding="utf-8")).get("summary")


def _case_redirect(dispute_id: str, notice: str | None = None) -> RedirectResponse:
    target = f"/disputes/{dispute_id}"
    if notice:
        target += f"?notice={quote(notice)}"
    return RedirectResponse(target, status_code=303)


# ---- public ----

@public_router.get("/health")
def health():
    return {"ok": True}


@public_router.get("/", response_class=HTMLResponse)
def home(request: Request):
    return TEMPLATES.TemplateResponse(request, "home.html", {"summary": eval_summary()})


@public_router.post("/webhooks/paypal")
async def paypal_webhook(request: Request, verifier=Depends(get_verifier)):
    body = await request.body()
    try:
        event = json.loads(body)
    except ValueError:
        raise HTTPException(400, "body is not valid JSON")
    headers = {k.lower(): v for k, v in request.headers.items()}
    try:
        verified = verifier.verify_webhook_signature(headers, event, config.PAYPAL_WEBHOOK_ID)
    except PayPalError as exc:
        raise HTTPException(502, f"verification failed: {exc}")
    if not verified:
        raise HTTPException(403, "signature not verified")
    resource = event.get("resource") or {}
    db.save_event(event.get("event_type", "UNKNOWN"), resource.get("dispute_id"), event)
    return {"ok": True}


# ---- protected: case board and case pages ----

@router.get("/disputes", response_class=HTMLResponse)
def inbox(request: Request, notice: str | None = None,
          user=Depends(current_user), paypal=Depends(get_paypal)):
    load_error = None
    try:
        raw = paypal.list_disputes()
    except PayPalError as exc:
        raw = []
        load_error = f"Could not load disputes from PayPal. {exc}"
    rows = [
        decorate(d, current_report(user["id"], d["id"], paypal), db.get_approval(user["id"], d["id"]))
        for d in raw
    ]
    open_rows = [r for r in rows if r["is_open"]]
    kpis = {
        "open": len(open_rows),
        "at_stake": float(sum(r["amount_value"] for r in open_rows)),
        "ready": sum(r["state"] == "ready" for r in rows),
        "approved": sum(1 for r in rows if r["approved_action"]),
    }
    return TEMPLATES.TemplateResponse(request, "inbox.html", {
        "disputes": rows, "kpis": kpis, "notice": notice, "load_error": load_error,
    })


@router.get("/disputes/{dispute_id}", response_class=HTMLResponse)
def detail(dispute_id: str, request: Request, error: str | None = None,
           notice: str | None = None, user=Depends(current_user), paypal=Depends(get_paypal)):
    try:
        raw = paypal.get_dispute(dispute_id)
    except DisputeNotFound:
        raise HTTPException(404, f"no dispute {dispute_id}")
    except PayPalError as exc:
        raise HTTPException(502, f"could not load {dispute_id} from PayPal: {exc}")
    report = current_report(user["id"], dispute_id, paypal)
    approval = db.get_approval(user["id"], dispute_id)
    records = db.get_records(user["id"], dispute_id)
    return TEMPLATES.TemplateResponse(request, "dispute.html", {
        "dispute": decorate(raw, report, approval),
        "report": report,
        "approved": approval["action"] if approval else None,
        "records": records,
        "record_count": sum(len(fields) for fields in records.values()),
        "error": error,
        "notice": notice,
    })


# ---- protected: records ----

@router.get("/records/sample.csv")
def sample_records():
    return Response(SAMPLE_RECORDS, media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="records-sample.csv"'})


@router.post("/disputes/{dispute_id}/records")
def save_records(dispute_id: str, csv_text: str = Form(""), file: UploadFile | None = File(None),
                 user=Depends(current_user), paypal=Depends(get_paypal)):
    try:
        paypal.get_dispute(dispute_id)
    except DisputeNotFound:
        raise HTTPException(404, f"no dispute {dispute_id}")

    text = csv_text
    if file is not None and file.filename:
        raw = file.file.read(MAX_UPLOAD_BYTES + 1)
        if len(raw) > MAX_UPLOAD_BYTES:
            return RedirectResponse(f"/disputes/{dispute_id}?error=File%20is%20larger%20than%20200%20KB.", status_code=303)
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            return RedirectResponse(f"/disputes/{dispute_id}?error=File%20must%20be%20UTF-8%20text.", status_code=303)

    try:
        mapping = parse_records_csv(text)
    except ValueError as exc:
        return RedirectResponse(f"/disputes/{dispute_id}?error={quote(str(exc))}", status_code=303)
    db.replace_records(user["id"], dispute_id, mapping)
    db.delete_approval(user["id"], dispute_id)
    return _case_redirect(dispute_id, "Records saved. Approval reset; check the gate again.")


# ---- protected: draft and approval ----

@router.post("/disputes/{dispute_id}/draft")
def draft(dispute_id: str, user=Depends(current_user), paypal=Depends(get_paypal), llm=Depends(get_llm)):
    try:
        report = run_draft(dispute_id, llm=llm, paypal=paypal,
                           merchant_records=db.get_records(user["id"], dispute_id))
    except DisputeNotFound:
        raise HTTPException(404, f"no dispute {dispute_id}")
    except (LLMOutputError, httpx.HTTPError, RuntimeError) as exc:
        raise HTTPException(502, f"model error: {exc}")
    db.save_draft(user["id"], dispute_id, report.draft)
    db.delete_approval(user["id"], dispute_id)
    return _case_redirect(dispute_id, "Draft ready. Review the gate before approving.")


@router.post("/disputes/{dispute_id}/approve")
def approve(dispute_id: str, user=Depends(current_user), paypal=Depends(get_paypal),
            submitter=Depends(get_submitter)):
    report = current_report(user["id"], dispute_id, paypal)
    if report is None:
        raise HTTPException(400, "generate a draft first")
    if report.action == HUMAN_REVIEW:
        raise HTTPException(400, "this case needs a human decision; nothing to approve")
    if report.blocked:
        raise HTTPException(409, "blocked by checks; fix the draft before approving")

    request_id = str(uuid.uuid4())
    paypal_response = None
    if submitter is not None:
        try:
            dispute = submitter.get_dispute(dispute_id)
            paypal_response = submit_report(report, dispute, submitter, request_id=request_id)
        except SubmissionRefused as exc:
            raise HTTPException(409, str(exc))
        except PayPalError as exc:
            raise HTTPException(502, f"PayPal rejected the submission: {exc}")
    db.save_approval(user["id"], dispute_id, report.action, request_id, paypal_response)
    notice = "Submitted to PayPal" if submitter is not None else "Approved (recorded only)"
    return _case_redirect(dispute_id, notice)


# ---- protected: PayPal connection settings ----

@router.get("/settings/paypal", response_class=HTMLResponse)
def paypal_settings(request: Request, notice: str | None = None, error: str | None = None,
                    user=Depends(current_user)):
    return TEMPLATES.TemplateResponse(request, "settings.html", {
        "status": credentials.status(user["id"]),
        "key_ready": bool(config.CREDENTIAL_KEY),
        "notice": notice,
        "error": error,
    })


@router.post("/settings/paypal")
def save_paypal(client_id: str = Form(""), client_secret: str = Form(""), env: str = Form("sandbox"),
                user=Depends(current_user)):
    try:
        credentials.save(user["id"], client_id.strip(), client_secret.strip(), env)
    except (ValueError, KeyMissing) as exc:
        return RedirectResponse(f"/settings/paypal?error={quote(str(exc))}", status_code=303)
    return RedirectResponse(
        "/settings/paypal?notice=" + quote(f"Credentials saved and encrypted. This account now reads PayPal {env} data."),
        status_code=303)


@router.post("/settings/paypal/test")
def test_paypal(user=Depends(current_user)):
    try:
        creds = credentials.load(user["id"])
    except KeyMissing as exc:
        return RedirectResponse(f"/settings/paypal?error={quote(str(exc))}", status_code=303)
    if creds is None:
        return RedirectResponse("/settings/paypal?error=Save%20your%20credentials%20first.", status_code=303)
    try:
        _client_for(creds).access_token()
    except PayPalError as exc:
        return RedirectResponse(f"/settings/paypal?error={quote(str(exc))}", status_code=303)
    return RedirectResponse("/settings/paypal?notice=" + quote("PayPal accepted these credentials."), status_code=303)


@router.post("/settings/paypal/delete")
def delete_paypal(user=Depends(current_user)):
    credentials.remove(user["id"])
    return RedirectResponse("/settings/paypal?notice=Disconnected.%20This%20account%20uses%20the%20demo%20data.",
                            status_code=303)
