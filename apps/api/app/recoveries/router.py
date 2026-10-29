from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.audit.actions import AuditAction
from app.audit.service import AuditService
from app.core.dependencies import get_current_organization
from app.db.database import get_db
from app.models.user import User
from app.recoveries.schemas import RecoveryRead, RecoveryVerify
from app.recoveries.service import RecoveryAttributionService
from app.security.dependencies import require_permission
from app.security.permissions import Permission

router = APIRouter(prefix="/recoveries", tags=["Recoveries"])


@router.get("", response_model=list[RecoveryRead])
def list_recoveries(
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.MANAGE_BILLING)),
):
    return RecoveryAttributionService(db, organization_id).list()


@router.post("/{recovery_id}/verify", response_model=RecoveryRead)
def verify_recovery(
    recovery_id: int,
    payload: RecoveryVerify,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.MANAGE_BILLING)),
):
    try:
        recovery = RecoveryAttributionService(db, organization_id).verify(
            recovery_id,
            verified_by=current_user.id,
            reason=payload.reason,
        )
        AuditService(db).log(
            organization_id=organization_id,
            user_id=current_user.id,
            action=AuditAction.RECOVERY_VERIFIED,
            entity="recovery",
            entity_id=recovery.id,
            metadata={
                "before": {"verified": False},
                "after": {"verified": True},
                "reason": recovery.verification_reason,
                "correlation_id": recovery.payment.correlation_id,
            },
        )
        db.commit()
        db.refresh(recovery)
        return recovery
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
