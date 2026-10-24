from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.web.routes import router

app = FastAPI(title="EvidenceGate")
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "web" / "static")), name="static")
app.include_router(router)
