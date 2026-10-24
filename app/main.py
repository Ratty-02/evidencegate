import base64
import secrets
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

from app import config, db
from app.web.routes import router

# Paths that skip the login: static assets, PayPal webhooks (checked by
# signature instead), and the health check.
OPEN_PREFIXES = ("/static", "/webhooks", "/health")


def _authorized(header: str) -> bool:
    if not header.startswith("Basic "):
        return False
    try:
        decoded = base64.b64decode(header[6:]).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return False
    user, _, password = decoded.partition(":")
    user_ok = secrets.compare_digest(user.encode(), config.APP_USER.encode())
    pass_ok = secrets.compare_digest(password.encode(), config.APP_PASSWORD.encode())
    return user_ok and pass_ok


@asynccontextmanager
async def lifespan(_app: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="EvidenceGate", lifespan=lifespan)


@app.middleware("http")
async def require_login(request: Request, call_next):
    """Login is enforced only when APP_PASSWORD is set (required for any hosted demo)."""
    if not config.APP_PASSWORD or request.url.path.startswith(OPEN_PREFIXES):
        return await call_next(request)
    if _authorized(request.headers.get("authorization", "")):
        return await call_next(request)
    return Response(
        "Login required",
        status_code=401,
        headers={"WWW-Authenticate": 'Basic realm="EvidenceGate"'},
    )


app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "web" / "static")), name="static")
app.include_router(router)
