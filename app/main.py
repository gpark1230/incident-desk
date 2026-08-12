from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.database import Base, engine
from app.routers import auth, incidents

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # No Alembic migrations yet -- this is a stand-in that creates any missing
    # tables on boot. Fine for a first deploy; a real migration tool is needed
    # before this app ever has data worth not losing on a schema change.
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="IncidentDesk API", lifespan=lifespan)

app.include_router(auth.router)
app.include_router(incidents.router)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
def frontend():
    return FileResponse(STATIC_DIR / "index.html")
