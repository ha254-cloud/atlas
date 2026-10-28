from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.recoveries.repository import RecoveryRepository
from app.recovery.schemas import BillingReadinessRead


class RecoveryBillingService:
    def __init__(self, db: Session, organization_id: int, currency: str) -> None:
        self.repository = RecoveryRepository(db, organization_id)
        self.currency = currency

    def readiness(self, period_start: date, period_end: date) -> BillingReadinessRead:
        recoveries = self.repository.verified_uninvoiced(period_start, period_end)
        recovered = sum((item.recovered_amount for item in recoveries), Decimal(0))
        fees = sum((item.atlas_fee_amount for item in recoveries), Decimal(0))
        return BillingReadinessRead(
            currency=self.currency,
            verified_uninvoiced_recovery_count=len(recoveries),
            recovered_amount=recovered,
            atlas_fee_amount=fees,
            ready=bool(recoveries),
        )
