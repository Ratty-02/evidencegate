import os
import secrets

from dotenv import load_dotenv

load_dotenv()


def _flag(name: str, default: str) -> bool:
    return os.getenv(name, default).strip().lower() == "true"


PAYPAL_MOCK = _flag("PAYPAL_MOCK", "true")
PAYPAL_ENV = os.getenv("PAYPAL_ENV", "sandbox")
PAYPAL_CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID", "")
PAYPAL_CLIENT_SECRET = os.getenv("PAYPAL_CLIENT_SECRET", "")
PAYPAL_WEBHOOK_ID = os.getenv("PAYPAL_WEBHOOK_ID", "")
# Signs session cookies. Set a long random value in production. If unset, a
# random value is generated at startup, which signs everyone out on restart.
SESSION_SECRET = os.getenv("SESSION_SECRET") or secrets.token_urlsafe(32)
SESSION_MAX_AGE_DAYS = int(os.getenv("SESSION_MAX_AGE_DAYS", "7"))
# Set true when served over HTTPS (for example on Render).
COOKIE_SECURE = _flag("COOKIE_SECURE", "false")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "openai/gpt-oss-120b")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./evidencegate.db")
