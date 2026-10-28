from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.billing.models import RecoveryFeeSchedule
from app.billing.repository import RecoveryFeeScheduleRepository


class RecoveryFeeScheduleService:
    def __init__(self, db: Session, organization_id: int) -> None:
        self.db = db
        self.organization_id = organization_id
        self.repository = RecoveryFeeScheduleRepository(db, organization_id)

    def effective_on(self, effective_date: date) -> RecoveryFeeSchedule:
        schedule = self.repository.effective_on(effective_date)
        if schedule is None:
            raise ValueError(f"No recovery fee schedule is effective on {effective_date}")
        return schedule

    def create(
        self,
        *,
        fee_percentage: Decimal,
        vat_percentage: Decimal,
        currency: str,
        payment_terms_days: int,
        dispute_period_days: int = 0,
        effective_from: date,
        effective_to: date | None,
        created_by: int | None,
        reason: str,
    ) -> RecoveryFeeSchedule:
        if not Decimal("0") <= fee_percentage <= Decimal("100"):
            raise ValueError("fee_percentage must be between 0 and 100")
        if not Decimal("0") <= vat_percentage <= Decimal("100"):
            raise ValueError("vat_percentage must be between 0 and 100")
        if effective_to is not None and effective_to < effective_from:
            raise ValueError("effective_to cannot be before effective_from")
        if payment_terms_days < 0 or payment_terms_days > 365:
            raise ValueError("payment_terms_days must be between 0 and 365")
        if dispute_period_days < 0 or dispute_period_days > 365:
            raise ValueError("dispute_period_days must be between 0 and 365")
        if not reason.strip():
            raise ValueError("reason is required")

        schedule = RecoveryFeeSchedule(
            organization_id=self.organization_id,
            fee_percentage=fee_percentage,
            vat_percentage=vat_percentage,
            currency=currency.upper(),
            payment_terms_days=payment_terms_days,
            dispute_period_days=dispute_period_days,
            effective_from=effective_from,
            effective_to=effective_to,
            created_by=created_by,
            reason=reason.strip(),
        )
        self.db.add(schedule)
        self.db.flush()
        return schedule
