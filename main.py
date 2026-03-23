from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from api.routes import router

app = FastAPI(title="Article Translator", version="1.0.0")

app.include_router(router)

static_dir = Path("static")
static_dir.mkdir(exist_ok=True)
app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
