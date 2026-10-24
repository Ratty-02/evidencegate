import os

from dotenv import load_dotenv

load_dotenv()


def _flag(name: str, default: str) -> bool:
    return os.getenv(name, default).strip().lower() == "true"


PAYPAL_MOCK = _flag("PAYPAL_MOCK", "true")
PAYPAL_ENV = os.getenv("PAYPAL_ENV", "sandbox")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./evidencegate.db")
