"""Web routes. Drafts and approvals are held in memory for this prototype.

Approval records the decision only. Nothing is sent to PayPal yet.
"""
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.ai.llm import GroqClient, LLMOutputError
from app.ai.pipeline import HUMAN_REVIEW, Report, run_draft
from app.paypal.mock_client import DisputeNotFound, MockPayPalClient

TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
router = APIRouter()

_paypal = MockPayPalClient()
REPORTS: dict[str, Report] = {}
APPROVED: dict[str, str] = {}


def get_paypal() -> MockPayPalClient:
    return _paypal


def get_llm() -> GroqClient:
    return GroqClient()


@router.get("/", response_class=HTMLResponse)
def inbox(request: Request, paypal=Depends(get_paypal)):
    return TEMPLATES.TemplateResponse(request, "inbox.html", {
        "disputes": paypal.list_disputes(),
        "approved": APPROVED,
    })


@router.get("/disputes/{dispute_id}", response_class=HTMLResponse)
def detail(dispute_id: str, request: Request, paypal=Depends(get_paypal)):
    try:
        dispute = paypal.get_dispute(dispute_id)
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
    APPROVED.pop(dispute_id, None)  # a new draft needs a new approval
    return RedirectResponse(f"/disputes/{dispute_id}", status_code=303)


@router.post("/disputes/{dispute_id}/approve")
def approve(dispute_id: str):
    report = REPORTS.get(dispute_id)
    if report is None:
        raise HTTPException(400, "generate a draft first")
    if report.action == HUMAN_REVIEW:
        raise HTTPException(400, "this case needs a human decision; nothing to approve")
    if report.blocked:
        raise HTTPException(409, "blocked by checks; fix the draft before approving")
    APPROVED[dispute_id] = report.action
    return RedirectResponse(f"/disputes/{dispute_id}", status_code=303)
