"""Sign up, sign in, and sign out. These pages are public."""
from urllib.parse import quote

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app import auth, config, db
from app.web.templating import TEMPLATES

router = APIRouter()


def _render(request: Request, mode: str, error: str | None = None, email: str = "", status: int = 200):
    return TEMPLATES.TemplateResponse(
        request, "auth.html", {"mode": mode, "error": error, "email": email}, status_code=status
    )


def _signed_in(user_id: int, notice: str | None = None) -> RedirectResponse:
    target = "/disputes" + (f"?notice={quote(notice)}" if notice else "")
    response = RedirectResponse(target, status_code=303)
    response.set_cookie(
        auth.COOKIE_NAME,
        auth.make_session_token(user_id),
        httponly=True,
        samesite="lax",
        secure=config.COOKIE_SECURE,
        max_age=config.SESSION_MAX_AGE_DAYS * 86400,
    )
    return response


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return _render(request, "login")


@router.post("/login", response_class=HTMLResponse)
def login(request: Request, email: str = Form(""), password: str = Form("")):
    email = email.strip().lower()
    user = db.get_user_by_email(email)
    if user is None or not auth.verify_password(password, user["password_hash"]):
        return _render(request, "login", error="Email or password is incorrect.", email=email, status=401)
    return _signed_in(user["id"], notice="Signed in")


@router.get("/signup", response_class=HTMLResponse)
def signup_page(request: Request):
    return _render(request, "signup")


@router.post("/signup", response_class=HTMLResponse)
def signup(request: Request, email: str = Form(""), password: str = Form("")):
    email = email.strip().lower()
    problem = auth.validate_signup(email, password)
    if problem:
        return _render(request, "signup", error=problem, email=email, status=400)
    try:
        user = db.create_user(email, auth.hash_password(password))
    except ValueError as exc:
        return _render(request, "signup", error=str(exc), email=email, status=409)
    return _signed_in(user["id"], notice="Account created. Welcome to EvidenceGate.")


@router.post("/logout")
def logout():
    response = RedirectResponse("/login?notice=Signed%20out", status_code=303)
    response.delete_cookie(auth.COOKIE_NAME)
    return response
