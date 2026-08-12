import os

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql://incident_desk_user:devpassword123@localhost:5432/incident_desk_test",
)
os.environ.setdefault("SECRET_KEY", "test-secret-key")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import User, UserRole  # noqa: E402
from app.security import hash_password  # noqa: E402

engine = create_engine(os.environ["DATABASE_URL"])
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def reset_db():
    """Wipes and recreates every table before each test, so tests never see leftover data."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def make_user():
    """Creates a user directly in the DB (bypassing signup), so tests can get an
    analyst or admin without the API ever exposing a way to self-promote to one."""

    def _make_user(email: str, password: str = "testpass123", role: UserRole = UserRole.viewer) -> User:
        db = TestingSessionLocal()
        user = User(email=email, hashed_password=hash_password(password), role=role)
        db.add(user)
        db.commit()
        db.refresh(user)
        db.close()
        return user

    return _make_user


@pytest.fixture
def auth_headers(client):
    def _auth_headers(email: str, password: str = "testpass123") -> dict:
        response = client.post("/auth/login", data={"username": email, "password": password})
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    return _auth_headers
