from pathlib import Path

from fastapi.templating import Jinja2Templates

from app import config

TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
TEMPLATES.env.globals["is_mock"] = lambda: config.PAYPAL_MOCK
