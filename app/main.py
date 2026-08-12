from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.routers import auth, incidents

STATIC_DIR = Path(__file__).parent / "static"

# Schema is now owned by Alembic migrations (see alembic/), run via
# `alembic upgrade head` before the app starts (Procfile / Dockerfile CMD) --
# not by the app itself at import/startup time. The app has no business
# creating or altering tables at runtime.
app = FastAPI(title="IncidentDesk API")

app.include_router(auth.router)
app.include_router(incidents.router)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
def frontend():
    return FileResponse(STATIC_DIR / "index.html")
