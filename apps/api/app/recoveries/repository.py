from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.models.recovery import Recovery


class RecoveryRepository:
    def __init__(self, db: Session, organization_id: int) -> None:
        self.db = db
        self.organization_id = organization_id

    def get(self, recovery_id: int) -> Recovery | None:
        return self.db.query(Recovery).filter(
            Recovery.id == recovery_id,
            Recovery.organization_id == self.organization_id,
        ).first()

    def for_submission(self, submission_id: int) -> Recovery | None:
        return self.db.query(Recovery).filter(
            Recovery.submission_id == submission_id,
            Recovery.organization_id == self.organization_id,
        ).first()

    def for_payment(self, payment_id: int) -> Recovery | None:
        return self.db.query(Recovery).filter(
            Recovery.payment_id == payment_id,
            Recovery.organization_id == self.organization_id,
        ).first()

    def for_payment_claim(self, payment_id: int, claim_id: int) -> Recovery | None:
        return self.db.query(Recovery).filter(
            Recovery.payment_id == payment_id,
            Recovery.claim_id == claim_id,
            Recovery.organization_id == self.organization_id,
        ).first()

    def list(self) -> list[Recovery]:
        return self.db.query(Recovery).filter(
            Recovery.organization_id == self.organization_id
        ).order_by(Recovery.payment_date.desc()).all()

    def verified_uninvoiced(self, period_start: date, period_end: date) -> list[Recovery]:
        return self.db.query(Recovery).filter(
            Recovery.organization_id == self.organization_id,
            Recovery.verified.is_(True),
            Recovery.payment_date >= period_start,
            Recovery.payment_date <= period_end,
            ~Recovery.invoice_line.has(),
        ).order_by(Recovery.payment_date, Recovery.id).all()
