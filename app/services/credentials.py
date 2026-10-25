"""Per-merchant PayPal credentials. Stored encrypted; decrypted only when used."""
from datetime import datetime, timezone

from app import db
from app.secrets_box import decrypt, encrypt

ALLOWED_ENVS = {"sandbox", "live"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def save(user_id: int, client_id: str, client_secret: str, env: str) -> None:
    if not client_id or not client_secret:
        raise ValueError("Client ID and client secret are both required.")
    if env not in ALLOWED_ENVS:
        raise ValueError("Environment must be sandbox or live.")
    db.save_paypal_credentials(
        user_id, env, encrypt(client_id), encrypt(client_secret), client_id[-4:], _now()
    )


def status(user_id: int) -> dict | None:
    """Safe to show in the UI: no secrets, only a hint of the client ID."""
    row = db.get_paypal_credentials(user_id)
    if row is None:
        return None
    return {"env": row["env"], "hint": row["client_hint"], "updated_at": row["updated_at"]}


def load(user_id: int) -> dict | None:
    row = db.get_paypal_credentials(user_id)
    if row is None:
        return None
    return {
        "client_id": decrypt(row["client_id_enc"]),
        "client_secret": decrypt(row["secret_enc"]),
        "env": row["env"],
    }


def remove(user_id: int) -> None:
    db.delete_paypal_credentials(user_id)
