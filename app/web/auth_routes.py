"""Sign up, email verification, sign in, password reset, and sign out. Public pages."""
import time
from urllib.parse import quote

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app import auth, config, db
from app.mailer import deliver
from app.web.templating import TEMPLATES

router = APIRouter()


def _page(request: Request, name: str, status: int = 200, **ctx):
    return TEMPLATES.TemplateResponse(request, name, ctx, status_code=status)


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


def _issue(user_id: int, email: str, purpose: str, subject: str, path: str, intro: str) -> str | None:
    """Create a one-time link, deliver it, and return it only in dev mode (for display)."""
    raw, digest = auth.new_token()
    db.create_auth_token(digest, user_id, purpose, time.time() + auth.TOKEN_TTL_SECONDS[purpose])
    link = f"{config.APP_BASE_URL.rstrip('/')}{path}{raw}"
    shown = deliver(email, subject, f"{intro}\n\n{link}\n\nIf you did not ask for this, ignore this email.")
    return link if shown else None


# ---- sign in and sign out ----

@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, error: str | None = None, notice: str | None = None):
    return _page(request, "auth.html", mode="login", error=error, notice=notice, email="", resend=False)


@router.post("/login", response_class=HTMLResponse)
def login(request: Request, email: str = Form(""), password: str = Form("")):
    email = email.strip().lower()
    now = time.time()
    since = now - config.LOGIN_WINDOW_SECONDS
    if db.count_login_failures(email, since) >= config.LOGIN_MAX_FAILURES:
        return _page(request, "auth.html", 429, mode="login", notice=None, resend=False, email=email,
                     error="Too many failed sign-in attempts. Wait 15 minutes, then try again.")
    user = db.get_user_by_email(email)
    if user is None or not auth.verify_password(password, user["password_hash"]):
        db.record_login_failure(email, now)
        return _page(request, "auth.html", 401, mode="login", notice=None, resend=False, email=email,
                     error="Email or password is incorrect.")
    if not user["email_verified"]:
        return _page(request, "auth.html", 403, mode="login", notice=None, resend=True, email=email,
                     error="Verify your email before signing in. Check your inbox for the link.")
    db.clear_login_failures(email)
    return _signed_in(user["id"], notice="Signed in")


@router.post("/logout")
def logout():
    response = RedirectResponse("/login?notice=Signed%20out", status_code=303)
    response.delete_cookie(auth.COOKIE_NAME)
    return response


# ---- sign up and verification ----

@router.get("/signup", response_class=HTMLResponse)
def signup_page(request: Request):
    return _page(request, "auth.html", mode="signup", error=None, notice=None, email="", resend=False)


@router.post("/signup", response_class=HTMLResponse)
def signup(request: Request, email: str = Form(""), password: str = Form("")):
    email = email.strip().lower()
    problem = auth.validate_signup(email, password)
    if problem:
        return _page(request, "auth.html", 400, mode="signup", error=problem, notice=None, email=email, resend=False)
    try:
        user = db.create_user(email, auth.hash_password(password), verified=False)
    except ValueError as exc:
        return _page(request, "auth.html", 409, mode="signup", error=str(exc), notice=None, email=email, resend=False)
    dev_link = _issue(user["id"], email, "verify", "Verify your EvidenceGate email", "/verify?token=",
                      "Confirm your email address to start using EvidenceGate.")
    return _page(request, "check_email.html", purpose="verify", email=email, dev_link=dev_link)


@router.get("/verify", response_class=HTMLResponse)
def verify(request: Request, token: str = ""):
    user_id = db.consume_auth_token(auth.hash_token(token), "verify", time.time()) if token else None
    if user_id is None:
        return _page(request, "message.html", 400, title="This link is not valid",
                     text="The verification link is invalid, already used, or expired. Request a new one below.",
                     dev_link=None, action_href="/login", action_label="Go to sign in")
    db.set_email_verified(user_id)
    return RedirectResponse("/login?notice=Email%20verified.%20You%20can%20sign%20in.", status_code=303)


@router.post("/resend-verification", response_class=HTMLResponse)
def resend_verification(request: Request, email: str = Form("")):
    email = email.strip().lower()
    dev_link = None
    user = db.get_user_by_email(email)
    if user is not None and not user["email_verified"]:
        dev_link = _issue(user["id"], email, "verify", "Verify your EvidenceGate email", "/verify?token=",
                          "Confirm your email address to start using EvidenceGate.")
    # Same response whether or not the account exists.
    return _page(request, "check_email.html", purpose="verify", email=email, dev_link=dev_link)


# ---- password reset ----

@router.get("/forgot", response_class=HTMLResponse)
def forgot_page(request: Request):
    return _page(request, "form.html", title="Reset your password",
                 lede="Enter the email you signed up with. We'll send a link that expires in one hour.",
                 action="/forgot", submit="Send reset link", error=None, hidden=None,
                 fields=[{"name": "email", "label": "Email", "type": "email", "autocomplete": "email",
                          "placeholder": "you@company.com", "value": "", "minlength": None}])


@router.post("/forgot", response_class=HTMLResponse)
def forgot(request: Request, email: str = Form("")):
    email = email.strip().lower()
    dev_link = None
    user = db.get_user_by_email(email)
    if user is not None:
        dev_link = _issue(user["id"], email, "reset", "Reset your EvidenceGate password", "/reset?token=",
                          "Use this link to choose a new password. It expires in one hour.")
    # Same message whether or not the account exists.
    return _page(request, "message.html", 200, title="Check your email",
                 text="If an account exists for that email, a reset link is on its way.",
                 dev_link=dev_link, action_href="/login", action_label="Back to sign in")


@router.get("/reset", response_class=HTMLResponse)
def reset_page(request: Request, token: str = ""):
    valid = token and db.peek_auth_token(auth.hash_token(token), "reset", time.time()) is not None
    if not valid:
        return _page(request, "message.html", 400, title="This link is not valid",
                     text="The reset link is invalid, already used, or expired. Request a new one.",
                     dev_link=None, action_href="/forgot", action_label="Request a new link")
    return _page(request, "form.html", title="Choose a new password",
                 lede="At least 8 characters.", action="/reset", submit="Save new password", error=None,
                 hidden={"token": token},
                 fields=[{"name": "password", "label": "New password", "type": "password",
                          "autocomplete": "new-password", "placeholder": "At least 8 characters",
                          "value": "", "minlength": 8}])


@router.post("/reset", response_class=HTMLResponse)
def reset(request: Request, token: str = Form(""), password: str = Form("")):
    if len(password or "") < auth.MIN_PASSWORD_LENGTH:
        return _page(request, "form.html", 400, title="Choose a new password",
                     lede="At least 8 characters.", action="/reset", submit="Save new password",
                     error=f"Password must be at least {auth.MIN_PASSWORD_LENGTH} characters.",
                     hidden={"token": token},
                     fields=[{"name": "password", "label": "New password", "type": "password",
                              "autocomplete": "new-password", "placeholder": "At least 8 characters",
                              "value": "", "minlength": 8}])
    user_id = db.consume_auth_token(auth.hash_token(token), "reset", time.time()) if token else None
    if user_id is None:
        return _page(request, "message.html", 400, title="This link is not valid",
                     text="The reset link is invalid, already used, or expired. Request a new one.",
                     dev_link=None, action_href="/forgot", action_label="Request a new link")
    db.update_password(user_id, auth.hash_password(password))
    return RedirectResponse("/login?notice=Password%20updated.%20Sign%20in%20with%20your%20new%20password.",
                            status_code=303)
