"""Authentication dependencies.

optional_user: reads the session if present (public pages use it for the header).
current_user:  requires a valid session AND a verified email. Otherwise the
               request is redirected to /login by handlers in app/main.py.
"""
from fastapi import Request

from app import auth, db


class NotAuthenticated(Exception):
    """No valid session."""


class NotVerified(Exception):
    """Signed in, but the email address has not been verified."""


def _session_user(request: Request) -> dict | None:
    token = request.cookies.get(auth.COOKIE_NAME)
    if not token:
        return None
    user_id = auth.read_session_token(token)
    return db.get_user(user_id) if user_id is not None else None


def optional_user(request: Request) -> dict | None:
    user = _session_user(request)
    request.state.user = user
    return user


def current_user(request: Request) -> dict:
    user = optional_user(request)
    if user is None:
        raise NotAuthenticated()
    if not user.get("email_verified"):
        raise NotVerified()
    return user
