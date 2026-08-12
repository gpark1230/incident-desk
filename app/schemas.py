from datetime import datetime

from pydantic import BaseModel, EmailStr

from app.models import IncidentStatus, Severity, UserRole


class UserCreate(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    email: EmailStr
    role: UserRole

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class IncidentCreate(BaseModel):
    title: str
    description: str | None = None
    severity: Severity
    assigned_to_id: int | None = None


class IncidentUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    severity: Severity | None = None
    status: IncidentStatus | None = None
    assigned_to_id: int | None = None


class IncidentOut(BaseModel):
    id: int
    title: str
    description: str | None
    severity: Severity
    status: IncidentStatus
    assigned_to_id: int | None
    created_by_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CommentCreate(BaseModel):
    body: str


class CommentOut(BaseModel):
    id: int
    incident_id: int
    author_id: int
    body: str
    created_at: datetime

    class Config:
        from_attributes = True


class AuditLogOut(BaseModel):
    id: int
    incident_id: int
    user_id: int
    action: str
    details: str | None
    created_at: datetime

    class Config:
        from_attributes = True
