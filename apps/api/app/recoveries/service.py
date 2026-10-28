from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from app.models.recovery import Recovery
from app.billing.models import RecoveryFeeSchedule
from app.payments.models import Payment
from app.recoveries.repository import RecoveryRepository

_MONEY = Decimal("0.01")


class RecoveryAttributionService:
    def __init__(self, db: Session, organization_id: int) -> None:
        self.db = db
        self.organization_id = organization_id
        self.repository = RecoveryRepository(db, organization_id)

    def record_payment(
        self,
        payment: Payment,
        *,
        fee_schedule: RecoveryFeeSchedule,
    ) -> Recovery:
        paid_amount = payment.paid_amount
        expected_amount = payment.expected_amount
        fee_percentage = fee_schedule.fee_percentage
        if paid_amount <= 0:
            raise ValueError("paid_amount must be greater than zero")
        if expected_amount < 0:
            raise ValueError("expected_amount cannot be negative")
        if fee_percentage < 0 or fee_percentage > 100:
            raise ValueError("fee_percentage must be between 0 and 100")
        if payment.organization_id != self.organization_id:
            raise ValueError("Payment belongs to another organization")
        if payment.claim_id is None:
            raise ValueError("Payment is not linked to a claim")
        if fee_schedule.organization_id != self.organization_id:
            raise ValueError("Fee schedule belongs to another organization")

        existing = self.repository.for_payment(payment.id)
        recovered_amount = paid_amount.quantize(_MONEY, rounding=ROUND_HALF_UP)
        fee_amount = (
            recovered_amount * fee_percentage / Decimal("100")
        ).quantize(_MONEY, rounding=ROUND_HALF_UP)
        recovery = existing or Recovery(
            organization_id=self.organization_id,
            claim_id=payment.claim_id,
            submission_id=payment.submission_id,
            payment_id=payment.id,
            verified=False,
        )
        recovery.paid_amount = paid_amount.quantize(_MONEY, rounding=ROUND_HALF_UP)
        recovery.expected_amount = expected_amount.quantize(_MONEY, rounding=ROUND_HALF_UP)
        recovery.recovered_amount = recovered_amount
        recovery.recovery_percentage = (
            recovered_amount / expected_amount * Decimal("100")
            if expected_amount > 0
            else Decimal("0")
        ).quantize(_MONEY, rounding=ROUND_HALF_UP)
        recovery.atlas_fee_percentage = fee_percentage.quantize(_MONEY)
        recovery.atlas_fee_amount = fee_amount
        recovery.payment_date = payment.payment_date
        if existing is None:
            self.db.add(recovery)
        self.db.flush()
        return recovery

    def verify(self, recovery_id: int, *, verified_by: int, reason: str) -> Recovery:
        recovery = self.get(recovery_id)
        if not reason.strip():
            raise ValueError("Verification reason is required")
        recovery.verified = True
        recovery.verified_by = verified_by
        recovery.verified_at = datetime.utcnow()
        recovery.verification_reason = reason.strip()
        self.db.flush()
        return recovery

    def get(self, recovery_id: int) -> Recovery:
        recovery = self.repository.get(recovery_id)
        if recovery is None:
            raise ValueError(f"Recovery {recovery_id} not found")
        return recovery

    def list(self) -> list[Recovery]:
        return self.repository.list()
