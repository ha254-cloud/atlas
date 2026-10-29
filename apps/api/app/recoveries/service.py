from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from app.billing.models import RecoveryFeeSchedule
from app.models.recovery import Recovery
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
        return self.record_allocation(
            payment,
            amount=payment.paid_amount,
            fee_schedule=fee_schedule,
        )

    def record_allocation(
        self,
        payment: Payment,
        *,
        amount: Decimal,
        fee_schedule: RecoveryFeeSchedule,
        claim_id: int | None = None,
        submission_id: int | None = None,
        expected_amount: Decimal | None = None,
    ) -> Recovery:
        paid_amount = amount
        resolved_expected_amount = expected_amount or payment.expected_amount
        fee_percentage = fee_schedule.fee_percentage
        if paid_amount <= 0:
            raise ValueError("paid_amount must be greater than zero")
        if resolved_expected_amount < 0:
            raise ValueError("expected_amount cannot be negative")
        if fee_percentage < 0 or fee_percentage > 100:
            raise ValueError("fee_percentage must be between 0 and 100")
        if payment.organization_id != self.organization_id:
            raise ValueError("Payment belongs to another organization")
        resolved_claim_id = claim_id or payment.claim_id
        if resolved_claim_id is None:
            raise ValueError("Payment is not linked to a claim")
        if fee_schedule.organization_id != self.organization_id:
            raise ValueError("Fee schedule belongs to another organization")

        existing = self.repository.for_payment_claim(payment.id, resolved_claim_id)
        existing_amount = existing.recovered_amount if existing else Decimal("0")
        recovered_amount = (existing_amount + paid_amount).quantize(
            _MONEY,
            rounding=ROUND_HALF_UP,
        )
        fee_amount = (
            recovered_amount * fee_percentage / Decimal("100")
        ).quantize(_MONEY, rounding=ROUND_HALF_UP)
        recovery = existing or Recovery(
            organization_id=self.organization_id,
            claim_id=resolved_claim_id,
            submission_id=submission_id or payment.submission_id,
            payment_id=payment.id,
            verified=False,
        )
        recovery.paid_amount = recovered_amount
        recovery.expected_amount = resolved_expected_amount.quantize(
            _MONEY,
            rounding=ROUND_HALF_UP,
        )
        recovery.recovered_amount = recovered_amount
        recovery.recovery_percentage = (
            recovered_amount / resolved_expected_amount * Decimal("100")
            if resolved_expected_amount > 0
            else Decimal("0")
        ).quantize(_MONEY, rounding=ROUND_HALF_UP)
        recovery.atlas_fee_percentage = fee_percentage.quantize(_MONEY)
        recovery.atlas_fee_amount = fee_amount
        recovery.payment_date = payment.payment_date
        if existing is None:
            self.db.add(recovery)
        self.db.flush()
        return recovery

    def apply_adjustment(
        self,
        *,
        payment: Payment,
        claim_id: int,
        net_amount: Decimal,
    ) -> Recovery:
        recovery = self.repository.for_payment_claim(payment.id, claim_id)
        if recovery is None:
            raise ValueError("Recovery projection not found for payment allocation")
        net_amount = net_amount.quantize(_MONEY, rounding=ROUND_HALF_UP)
        recovery.paid_amount = net_amount
        recovery.recovered_amount = net_amount
        recovery.recovery_percentage = (
            net_amount / recovery.expected_amount * Decimal("100")
            if recovery.expected_amount > 0
            else Decimal("0")
        ).quantize(_MONEY, rounding=ROUND_HALF_UP)
        recovery.atlas_fee_amount = (
            net_amount * recovery.atlas_fee_percentage / Decimal("100")
        ).quantize(_MONEY, rounding=ROUND_HALF_UP)
        if recovery.invoice_line is None:
            recovery.verified = False
            recovery.verified_by = None
            recovery.verified_at = None
            recovery.verification_reason = None
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
