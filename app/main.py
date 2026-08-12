from fastapi import FastAPI

from app.database import Base, engine
from app.routers import auth, incidents

app = FastAPI(title="IncidentDesk API")

app.include_router(auth.router)
app.include_router(incidents.router)


@app.on_event("startup")
def create_tables():
    # No Alembic migrations yet -- this is a stand-in that creates any missing
    # tables on boot. Fine for a first deploy; a real migration tool is needed
    # before this app ever has data worth not losing on a schema change.
    Base.metadata.create_all(bind=engine)


@app.get("/health")
def health():
    return {"status": "ok"}
