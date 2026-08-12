from fastapi import FastAPI

from app.routers import auth

app = FastAPI(title="IncidentDesk API")

app.include_router(auth.router)


@app.get("/health")
def health():
    return {"status": "ok"}
