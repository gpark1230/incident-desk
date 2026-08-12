from fastapi import FastAPI

from app.routers import auth, incidents

app = FastAPI(title="IncidentDesk API")

app.include_router(auth.router)
app.include_router(incidents.router)


@app.get("/health")
def health():
    return {"status": "ok"}
