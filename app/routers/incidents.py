import enum
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_role
from app.database import get_db
from app.events import publish_event
from app.models import AuditLog, Comment, Incident, IncidentStatus, Severity, User, UserRole
from app.schemas import AuditLogOut, CommentCreate, CommentOut, IncidentCreate, IncidentOut, IncidentUpdate

router = APIRouter(prefix="/incidents", tags=["incidents"])


def _fmt(value: object) -> str:
    """Renders enum members as their plain value (e.g. 'high', not 'Severity.high')."""
    return value.value if isinstance(value, enum.Enum) else str(value)


def _log_audit(db: Session, incident_id: int, user_id: int, action: str, details: str | None = None) -> None:
    db.add(AuditLog(incident_id=incident_id, user_id=user_id, action=action, details=details))


@router.post("", response_model=IncidentOut, status_code=status.HTTP_201_CREATED)
def create_incident(
    incident_in: IncidentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.analyst, UserRole.admin)),
):
    incident = Incident(
        title=incident_in.title,
        description=incident_in.description,
        severity=incident_in.severity,
        assigned_to_id=incident_in.assigned_to_id,
        created_by_id=current_user.id,
    )
    db.add(incident)
    db.flush()  # assigns incident.id without ending the transaction, so the audit row can reference it

    _log_audit(
        db,
        incident_id=incident.id,
        user_id=current_user.id,
        action="created",
        details=f"severity: {_fmt(incident.severity)}",
    )
    publish_event(
        "incident.created",
        incident_id=incident.id,
        user_id=current_user.id,
        details=f"severity: {_fmt(incident.severity)}",
    )

    db.commit()
    db.refresh(incident)
    return incident


@router.get("", response_model=list[IncidentOut])
def list_incidents(
    status_: IncidentStatus | None = Query(None, alias="status"),
    severity: Severity | None = None,
    assigned_to_id: int | None = None,
    created_after: datetime | None = None,
    created_before: datetime | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Incident)

    if status_ is not None:
        query = query.filter(Incident.status == status_)
    if severity is not None:
        query = query.filter(Incident.severity == severity)
    if assigned_to_id is not None:
        query = query.filter(Incident.assigned_to_id == assigned_to_id)
    if created_after is not None:
        query = query.filter(Incident.created_at >= created_after)
    if created_before is not None:
        query = query.filter(Incident.created_at <= created_before)

    return (
        query.order_by(Incident.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.get("/{incident_id}", response_model=IncidentOut)
def get_incident(
    incident_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    incident = db.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")
    return incident


@router.patch("/{incident_id}", response_model=IncidentOut)
def update_incident(
    incident_id: int,
    incident_in: IncidentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.analyst, UserRole.admin)),
):
    incident = db.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")

    updates = incident_in.model_dump(exclude_unset=True)
    changes = []
    for field, new_value in updates.items():
        old_value = getattr(incident, field)
        if old_value != new_value:
            changes.append(f"{field}: {_fmt(old_value)} -> {_fmt(new_value)}")
            setattr(incident, field, new_value)

    if changes:
        _log_audit(
            db,
            incident_id=incident.id,
            user_id=current_user.id,
            action="updated",
            details="; ".join(changes),
        )
        publish_event(
            "incident.updated",
            incident_id=incident.id,
            user_id=current_user.id,
            details="; ".join(changes),
        )

    db.commit()
    db.refresh(incident)
    return incident


@router.post("/{incident_id}/comments", response_model=CommentOut, status_code=status.HTTP_201_CREATED)
def create_comment(
    incident_id: int,
    comment_in: CommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.analyst, UserRole.admin)),
):
    incident = db.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")

    comment = Comment(incident_id=incident_id, author_id=current_user.id, body=comment_in.body)
    db.add(comment)

    _log_audit(
        db,
        incident_id=incident_id,
        user_id=current_user.id,
        action="commented",
        details=comment_in.body[:100],
    )
    publish_event(
        "incident.commented",
        incident_id=incident_id,
        user_id=current_user.id,
        details=comment_in.body[:100],
    )

    db.commit()
    db.refresh(comment)
    return comment


@router.get("/{incident_id}/comments", response_model=list[CommentOut])
def list_comments(
    incident_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    incident = db.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")

    return (
        db.query(Comment)
        .filter(Comment.incident_id == incident_id)
        .order_by(Comment.created_at.asc())
        .all()
    )


@router.get("/{incident_id}/audit-log", response_model=list[AuditLogOut])
def get_incident_audit_log(
    incident_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    incident = db.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")

    return (
        db.query(AuditLog)
        .filter(AuditLog.incident_id == incident_id)
        .order_by(AuditLog.created_at.asc())
        .all()
    )
