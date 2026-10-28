from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_organization
from app.db.database import get_db
from app.models.user import User
from app.organizations.schemas import (
    OrganizationProfileUpdate,
    OrganizationResponse,
    OrganizationSettingsResponse,
    OrganizationSettingsUpdate,
    OrganizationSettingsVersionResponse,
)
from app.organizations.service import OrganizationService
from app.security.dependencies import get_current_user, require_permission
from app.security.permissions import Permission

router = APIRouter(prefix="/organizations", tags=["Organizations"])


@router.get("/current", response_model=OrganizationResponse)
def get_current_organization_profile(
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
):
    try:
        return OrganizationService(db, organization_id).get()
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/current", response_model=OrganizationResponse)
def update_current_organization_profile(
    payload: OrganizationProfileUpdate,
    request: Request,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.MANAGE_ORGANIZATION)),
):
    return OrganizationService(db, organization_id).update_profile(
        payload,
        actor_id=current_user.id,
        correlation_id=getattr(request.state, "request_id", None),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


@router.get("/current/settings", response_model=OrganizationSettingsResponse)
def get_current_organization_settings(
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    _current_user: User = Depends(get_current_user),
):
    service = OrganizationService(db, organization_id)
    return OrganizationSettingsResponse(
        organization_id=organization_id,
        version=service.settings_version(),
        settings=service.settings(),
    )


@router.put("/current/settings", response_model=OrganizationSettingsVersionResponse)
def update_current_organization_settings(
    payload: OrganizationSettingsUpdate,
    request: Request,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.MANAGE_ORGANIZATION)),
):
    return OrganizationService(db, organization_id).update_settings(
        payload,
        actor_id=current_user.id,
        correlation_id=getattr(request.state, "request_id", None),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


@router.get(
    "/current/settings/history",
    response_model=list[OrganizationSettingsVersionResponse],
)
def list_current_organization_settings_history(
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    _current_user: User = Depends(require_permission(Permission.MANAGE_ORGANIZATION)),
):
    return OrganizationService(db, organization_id).list_settings_versions()


@router.get("/{organization_id}", response_model=OrganizationResponse)
def get_organization(
    organization_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization = OrganizationService(db, current_user.organization_id).get_by_id(organization_id)
    if organization is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    return organization
