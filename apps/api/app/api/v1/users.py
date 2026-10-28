from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_organization
from app.db.database import get_db
from app.models.user import User
from app.schemas.auth import TokenResponse
from app.schemas.invitation import AcceptInviteRequest, InviteRequest, InviteResponse, UserRead
from app.security.dependencies import require_permission
from app.security.permissions import Permission
from app.services.invitation_service import InvitationService

router = APIRouter(
    prefix="/users",
    tags=["Users"],
)


@router.get("", response_model=list[UserRead])
def list_organization_members(
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
):
    """List every user belonging to the current organization."""
    return (
        db.query(User)
        .filter(User.organization_id == organization_id)
        .order_by(User.created_at)
        .all()
    )


@router.post("/invite", response_model=InviteResponse)
def invite_user(
    payload: InviteRequest,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.MANAGE_USERS)),
):
    """Invite a teammate to join the current organization. Requires the MANAGE_USERS permission."""
    try:
        invitation = InvitationService(db, organization_id).invite(
            payload.email,
            payload.role,
            invited_by=current_user.id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "invitation_id": invitation.id,
        "email": invitation.email,
        "role": invitation.role,
        "message": "Invitation sent",
    }


@router.post("/accept-invite", response_model=TokenResponse)
def accept_invite(
    payload: AcceptInviteRequest,
    db: Session = Depends(get_db),
):
    """Join an organization using an invitation token. Never creates a new
    organization — the invited user joins the inviter's existing org."""
    try:
        return InvitationService(db).accept(
            payload.token,
            payload.first_name,
            payload.last_name,
            payload.password,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
