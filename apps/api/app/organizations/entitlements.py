from enum import StrEnum

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.user import User
from app.organizations.service import OrganizationService
from app.security.dependencies import get_current_user


class Feature(StrEnum):
    AI_ANALYSIS = "ai_analysis"
    AI_APPEAL = "ai_appeal"
    PAYMENT_TRACKING = "payment_tracking"
    ANALYTICS = "analytics"
    COPILOT = "copilot"
    PORTAL_AUTOMATION = "portal_automation"


def require_feature(feature: Feature):
    def dependency(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        settings = OrganizationService(db, current_user.organization_id).settings()
        if not getattr(settings.features, feature.value):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Feature '{feature.value}' is not enabled for this organization",
            )
        return current_user

    return dependency
