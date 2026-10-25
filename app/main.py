import logging
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import db
from app.web import auth_routes
from app.web.deps import NotAuthenticated, NotVerified
from app.web.routes import public_router, router
from app.web.templating import TEMPLATES

log = logging.getLogger("evidencegate")

FRIENDLY = {
    400: "That request could not be completed.",
    401: "Please sign in to continue.",
    403: "You do not have access to this page.",
    404: "We could not find that page or dispute.",
    409: "This action is blocked right now.",
    429: "Too many attempts. Please wait a few minutes and try again.",
    502: "PayPal or the AI model did not respond as expected. Please try again shortly.",
    503: "This feature is not available right now.",
}
SHOW_DETAIL = {400, 409, 429, 502, 503}


def _wants_html(request: Request) -> bool:
    return request.url.path.startswith("/webhooks") is False and "text/html" in request.headers.get("accept", "")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="EvidenceGate", lifespan=lifespan)


@app.exception_handler(NotAuthenticated)
async def redirect_to_login(request: Request, exc: NotAuthenticated):
    return RedirectResponse("/login", status_code=303)


@app.exception_handler(NotVerified)
async def redirect_unverified(request: Request, exc: NotVerified):
    message = quote("Verify your email before opening your workspace.")
    return RedirectResponse(f"/login?error={message}", status_code=303)


@app.exception_handler(StarletteHTTPException)
async def friendly_http_errors(request: Request, exc: StarletteHTTPException):
    if not _wants_html(request):
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
    detail = str(exc.detail) if exc.status_code in SHOW_DETAIL else None
    return TEMPLATES.TemplateResponse(
        request, "error.html",
        {"code": exc.status_code, "message": FRIENDLY.get(exc.status_code, "Something went wrong."),
         "detail": detail},
        status_code=exc.status_code,
    )


@app.exception_handler(Exception)
async def unexpected_error(request: Request, exc: Exception):
    log.exception("unhandled error on %s", request.url.path)
    if not _wants_html(request):
        return JSONResponse({"detail": "internal error"}, status_code=500)
    return TEMPLATES.TemplateResponse(
        request, "error.html",
        {"code": 500, "message": "Something went wrong on our side. The team has been notified.", "detail": None},
        status_code=500,
    )


app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "web" / "static")), name="static")
app.include_router(auth_routes.router)
app.include_router(public_router)
app.include_router(router)
