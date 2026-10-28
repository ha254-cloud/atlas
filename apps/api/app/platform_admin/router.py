from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.user import User
from app.platform_admin.schemas import HospitalSummary, PlatformAdminSummary
from app.platform_admin.service import PlatformAdminService
from app.security.dependencies import require_superuser

router = APIRouter(prefix="/platform-admin", tags=["Platform Administration"])


@router.get("/summary", response_model=PlatformAdminSummary)
def get_platform_admin_summary(
    current_user: User = Depends(require_superuser),
    db: Session = Depends(get_db),
):
    return PlatformAdminService(db, current_user).summary()


@router.get("/hospitals", response_model=list[HospitalSummary])
def list_platform_hospitals(
    current_user: User = Depends(require_superuser),
    db: Session = Depends(get_db),
):
    return PlatformAdminService(db, current_user).hospitals()
