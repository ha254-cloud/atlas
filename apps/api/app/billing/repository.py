from datetime import date

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.billing.models import RecoveryFeeSchedule


class RecoveryFeeScheduleRepository:
    def __init__(self, db: Session, organization_id: int) -> None:
        self.db = db
        self.organization_id = organization_id

    def effective_on(self, effective_date: date) -> RecoveryFeeSchedule | None:
        return self.db.query(RecoveryFeeSchedule).filter(
            RecoveryFeeSchedule.organization_id == self.organization_id,
            RecoveryFeeSchedule.effective_from <= effective_date,
            or_(
                RecoveryFeeSchedule.effective_to.is_(None),
                RecoveryFeeSchedule.effective_to >= effective_date,
            ),
        ).order_by(
            RecoveryFeeSchedule.effective_from.desc(),
            RecoveryFeeSchedule.id.desc(),
        ).first()

    def list(self) -> list[RecoveryFeeSchedule]:
        return self.db.query(RecoveryFeeSchedule).filter(
            RecoveryFeeSchedule.organization_id == self.organization_id
        ).order_by(RecoveryFeeSchedule.effective_from.desc()).all()
