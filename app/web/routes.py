"""Web routes. Drafts and approvals are held in memory for this prototype.

Approval records the decision only. Nothing is sent to PayPal yet.
"""
import json
import uuid
from datetime import date
from decimal import Decimal
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.ai.llm import GroqClient, LLMOutputError
from app.ai.pipeline import HUMAN_REVIEW, Report, run_draft
from app import config
from app.paypal.client import PayPalError, RealPayPalClient
from app.paypal.mock_client import DisputeNotFound, MockPayPalClient
from app.services.submission import SubmissionRefused, submit_report
from app.rules.paypal_evidence import ACTIONABLE_STATUS

ROOT = Path(__file__).resolve().parents[2]
OFFLINE_RESULTS = ROOT / "evals" / "results" / "offline.json"
TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
router = APIRouter()

_paypal = MockPayPalClient()
REPORTS: dict[str, Report] = {}
APPROVED: dict[str, str] = {}


def get_paypal() -> MockPayPalClient:
    return _paypal


def get_llm() -> GroqClient:
    return GroqClient()


def days_left(deadline: str) -> int:
    return (date.fromisoformat(deadline) - date.today()).days


def deadline_tone(days: int, is_open: bool) -> str:
    if not is_open:
        return "muted"
    if days <= 3:
        return "red"
    if days <= 7:
        return "amber"
    return "green"


def eval_summary() -> dict | None:
    if not OFFLINE_RESULTS.exists():
        return None
    return json.loads(OFFLINE_RESULTS.read_text(encoding="utf-8")).get("summary")


def decorate(d: dict) -> dict:
    is_open = d["status"] == ACTIONABLE_STATUS
    days = days_left(d["deadline"])
    report = REPORTS.get(d["id"])
    if d["id"] in APPROVED:
        state = "approved"
    elif report is None:
        state = "no-draft"
    elif report.blocked:
        state = "blocked"
    elif report.action == HUMAN_REVIEW:
        state = "review"
    else:
        state = "ready"
    return {
        **d,
        "is_open": is_open,
        "days_left": days,
        "deadline_tone": deadline_tone(days, is_open),
        "state": state,
        "approved_action": APPROVED.get(d["id"]),
        "amount_value": Decimal(d["amount"]),
    }


@router.get("/", response_class=HTMLResponse)
def home(request: Request):
    return TEMPLATES.TemplateResponse(request, "home.html", {"summary": eval_summary()})


@router.get("/disputes", response_class=HTMLResponse)
def inbox(request: Request, paypal=Depends(get_paypal)):
    rows = [decorate(d) for d in paypal.list_disputes()]
    open_rows = [r for r in rows if r["is_open"]]
    kpis = {
        "open": len(open_rows),
        "at_stake": float(sum(r["amount_value"] for r in open_rows)),
        "ready": sum(r["state"] == "ready" for r in rows),
        "approved": len(APPROVED),
    }
    return TEMPLATES.TemplateResponse(request, "inbox.html", {"disputes": rows, "kpis": kpis})


@router.get("/disputes/{dispute_id}", response_class=HTMLResponse)
def detail(dispute_id: str, request: Request, paypal=Depends(get_paypal)):
    try:
        dispute = decorate(paypal.get_dispute(dispute_id))
    except DisputeNotFound:
        raise HTTPException(404, f"no dispute {dispute_id}")
    return TEMPLATES.TemplateResponse(request, "dispute.html", {
        "dispute": dispute,
        "report": REPORTS.get(dispute_id),
        "approved": APPROVED.get(dispute_id),
    })


@router.post("/disputes/{dispute_id}/draft")
def draft(dispute_id: str, paypal=Depends(get_paypal), llm=Depends(get_llm)):
    try:
        REPORTS[dispute_id] = run_draft(dispute_id, llm=llm, paypal=paypal)
    except DisputeNotFound:
        raise HTTPException(404, f"no dispute {dispute_id}")
    except (LLMOutputError, httpx.HTTPError, RuntimeError) as exc:
        raise HTTPException(502, f"model error: {exc}")
    APPROVED.pop(dispute_id, None)
    return RedirectResponse(f"/disputes/{dispute_id}", status_code=303)


def get_submitter():
    """None in mock mode (decision recorded only). A real client otherwise."""
    return None if config.PAYPAL_MOCK else RealPayPalClient()


@router.post("/disputes/{dispute_id}/approve")
def approve(dispute_id: str, submitter=Depends(get_submitter)):
    report = REPORTS.get(dispute_id)
    if report is None:
        raise HTTPException(400, "generate a draft first")
    if report.action == HUMAN_REVIEW:
        raise HTTPException(400, "this case needs a human decision; nothing to approve")
    if report.blocked:
        raise HTTPException(409, "blocked by checks; fix the draft before approving")
    if submitter is not None:
        try:
            dispute = submitter.get_dispute(dispute_id)
            submit_report(report, dispute, submitter, request_id=str(uuid.uuid4()))
        except SubmissionRefused as exc:
            raise HTTPException(409, str(exc))
        except PayPalError as exc:
            raise HTTPException(502, f"PayPal rejected the submission: {exc}")
    APPROVED[dispute_id] = report.action
    return RedirectResponse(f"/disputes/{dispute_id}", status_code=303)
