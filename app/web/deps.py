"""Authentication dependencies.

optional_user: reads the session if present; used by public pages to show
               the right header.
current_user:  requires a valid session; otherwise the request is redirected
               to /login by the handler registered in app/main.py.
"""
from fastapi import Request

from app import auth, db


class NotAuthenticated(Exception):
    """Raised when a protected page is requested without a valid session."""


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
    return user
