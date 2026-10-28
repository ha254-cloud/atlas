from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_organization
from app.db.database import get_db
from app.models.user import User
from app.organizations.entitlements import Feature, require_feature
from app.security.dependencies import require_permission
from app.security.permissions import Permission
from app.services.dashboard_service import DashboardService

router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"],
    dependencies=[Depends(require_feature(Feature.ANALYTICS))],
)


@router.get("/summary")
def get_summary(
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.VIEW_ANALYTICS)),
) -> dict:
    """
    Return a high-level summary of claims, denials, and recovery opportunities
    for the authenticated organization.

    Example response:
        {
            "claims": 12543,
            "denied_claims": 734,
            "recovery_opportunities": 218,
            "estimated_recovery": 481235.50,
            "high_priority": 42
        }
    """
    return DashboardService(db, organization_id).get_summary()
