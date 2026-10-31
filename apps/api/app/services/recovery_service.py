from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from app.models.recovery import Recovery
from app.models.submission import Submission

_MONEY = Decimal("0.01")


class RecoveryAttributionService:
    def __init__(self, db: Session, organization_id: int) -> None:
        self.db = db
        self.organization_id = organization_id

    def record_payment(
        self,
        submission: Submission,
        *,
        paid_amount: Decimal,
        expected_amount: Decimal,
        fee_percentage: Decimal = Decimal("5.00"),
        payment_date: date | None = None,
    ) -> Recovery:
        if paid_amount <= 0:
            raise ValueError("paid_amount must be greater than zero")
        if expected_amount < 0:
            raise ValueError("expected_amount cannot be negative")
        if fee_percentage < 0 or fee_percentage > 100:
            raise ValueError("fee_percentage must be between 0 and 100")
        if submission.organization_id != self.organization_id:
            raise ValueError("Submission belongs to another organization")
        if submission.claim_id is None:
            raise ValueError("Submission is not linked to a claim")

        existing = self.db.query(Recovery).filter(
            Recovery.submission_id == submission.id,
            Recovery.organization_id == self.organization_id,
        ).first()
        recovered_amount = paid_amount.quantize(_MONEY, rounding=ROUND_HALF_UP)
        fee_amount = (
            recovered_amount * fee_percentage / Decimal("100")
        ).quantize(_MONEY, rounding=ROUND_HALF_UP)
        recovery = existing or Recovery(
            organization_id=self.organization_id,
            claim_id=submission.claim_id,
            submission_id=submission.id,
            verified=False,
        )
        recovery.paid_amount = paid_amount.quantize(_MONEY, rounding=ROUND_HALF_UP)
        recovery.expected_amount = expected_amount.quantize(_MONEY, rounding=ROUND_HALF_UP)
        recovery.recovered_amount = recovered_amount
        recovery.atlas_fee_percentage = fee_percentage.quantize(_MONEY)
        recovery.atlas_fee_amount = fee_amount
        recovery.payment_date = payment_date or date.today()
        if existing is None:
            self.db.add(recovery)
        self.db.flush()
        return recovery

    def verify(self, recovery_id: int) -> Recovery:
        recovery = self.get(recovery_id)
        recovery.verified = True
        self.db.flush()
        return recovery

    def get(self, recovery_id: int) -> Recovery:
        recovery = self.db.query(Recovery).filter(
            Recovery.id == recovery_id,
            Recovery.organization_id == self.organization_id,
        ).first()
        if recovery is None:
            raise ValueError(f"Recovery {recovery_id} not found")
        return recovery
