from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_organization
from app.db.database import get_db
from app.models.user import User
from app.patients.schemas import PatientCreate, PatientRead, PatientUpdate
from app.patients.service import PatientConflictError, PatientService
from app.security.dependencies import require_permission
from app.security.permissions import Permission

router = APIRouter(prefix="/patients", tags=["Patients"])


def _service(db: Session, organization_id: int) -> PatientService:
    return PatientService(db, organization_id)


@router.get("", response_model=list[PatientRead])
def list_patients(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    search: str | None = Query(default=None, min_length=1, max_length=100),
    date_of_birth: date | None = None,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.VIEW_PATIENTS)),
):
    return _service(db, organization_id).list_patients(
        limit=limit,
        offset=offset,
        search=search,
        date_of_birth=date_of_birth,
    )


@router.post("", response_model=PatientRead, status_code=status.HTTP_201_CREATED)
def create_patient(
    payload: PatientCreate,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.CREATE_PATIENTS)),
):
    try:
        return _service(db, organization_id).create_patient(payload, actor_id=current_user.id)
    except PatientConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("/{patient_id}", response_model=PatientRead)
def get_patient(
    patient_id: int,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.VIEW_PATIENTS)),
):
    patient = _service(db, organization_id).get_patient(patient_id)
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    return patient


@router.put("/{patient_id}", response_model=PatientRead)
def update_patient(
    patient_id: int,
    payload: PatientUpdate,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.EDIT_PATIENTS)),
):
    try:
        patient = _service(db, organization_id).update_patient(
            patient_id,
            payload,
            actor_id=current_user.id,
        )
    except PatientConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    return patient
