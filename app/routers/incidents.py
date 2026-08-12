from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_role
from app.database import get_db
from app.models import Incident, User, UserRole
from app.schemas import IncidentCreate, IncidentOut, IncidentUpdate

router = APIRouter(prefix="/incidents", tags=["incidents"])


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
    db.commit()
    db.refresh(incident)
    return incident


@router.get("", response_model=list[IncidentOut])
def list_incidents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.query(Incident).order_by(Incident.created_at.desc()).all()


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
    for field, value in updates.items():
        setattr(incident, field, value)

    db.commit()
    db.refresh(incident)
    return incident
