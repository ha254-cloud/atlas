from datetime import date
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.finance.analytics import outstanding
from app.models.claim import Claim
from app.models.denial import Denial
from app.models.payer import Payer
from app.models.recovery import Recovery
from app.models.recovery_case import RecoveryCase, RecoveryStatus
from app.payments.models import Payment, PaymentStatus


class FinanceRepository:
    def __init__(self, db: Session, organization_id: int) -> None:
        self.db = db
        self.organization_id = organization_id

    def claims(self) -> list[Claim]:
        return self.db.query(Claim).filter(Claim.organization_id == self.organization_id).all()

    def recoverable_by_claim(self) -> dict[int, tuple[Decimal, Decimal]]:
        rows = (
            self.db.query(
                RecoveryCase.claim_id,
                RecoveryCase.estimated_value,
                RecoveryCase.recovery_score,
            )
            .filter(
                RecoveryCase.organization_id == self.organization_id,
                RecoveryCase.status.in_(
                    [
                        RecoveryStatus.OPEN,
                        RecoveryStatus.IN_PROGRESS,
                        RecoveryStatus.APPEALED,
                    ]
                ),
            )
            .all()
        )
        result: dict[int, tuple[Decimal, Decimal]] = {}
        for claim_id, estimated_value, recovery_score in rows:
            current_amount, current_score = result.get(claim_id, (Decimal(0), Decimal(0)))
            result[claim_id] = (
                current_amount + (estimated_value or Decimal(0)),
                max(current_score, recovery_score or Decimal(0)),
            )
        return result

    def payments(self) -> list[tuple[int | None, Decimal, str, date]]:
        return (
            self.db.query(
                Payment.claim_id,
                Payment.paid_amount,
                Payment.currency,
                Payment.payment_date,
            )
            .filter(
                Payment.organization_id == self.organization_id,
                Payment.status.in_([PaymentStatus.PAID, PaymentStatus.PARTIAL]),
                Payment.paid_amount > 0,
            )
            .all()
        )

    def attributed_recoveries_total(self, currency: str) -> Decimal:
        return self.db.query(func.sum(Recovery.recovered_amount)).join(
            Payment, Recovery.payment_id == Payment.id
        ).filter(
            Recovery.organization_id == self.organization_id,
            Payment.organization_id == self.organization_id,
            Payment.currency == currency,
        ).scalar() or Decimal(0)

    def payer_rows(self, currency: str) -> list[dict]:
        claims = (
            self.db.query(Claim, Payer)
            .join(Payer, Claim.payer_id == Payer.id)
            .filter(
                Claim.organization_id == self.organization_id,
                Payer.organization_id == self.organization_id,
            )
            .all()
        )
        payments = (
            self.db.query(Payment, Claim)
            .join(Claim, Payment.claim_id == Claim.id)
            .filter(
                Payment.organization_id == self.organization_id,
                Claim.organization_id == self.organization_id,
                Payment.currency == currency,
                Payment.status.in_([PaymentStatus.PAID, PaymentStatus.PARTIAL]),
                Payment.paid_amount > 0,
            )
            .all()
        )
        recoveries = (
            self.db.query(Recovery, Claim)
            .join(Claim, Recovery.claim_id == Claim.id)
            .join(Payment, Recovery.payment_id == Payment.id)
            .filter(
                Recovery.organization_id == self.organization_id,
                Claim.organization_id == self.organization_id,
                Payment.organization_id == self.organization_id,
                Payment.currency == currency,
            )
            .all()
        )

        grouped: dict[int, dict] = {}
        for claim, payer in claims:
            row = grouped.setdefault(
                payer.id,
                {
                    "payer_id": payer.id,
                    "payer": payer.name,
                    "claim_count": 0,
                    "denied_count": 0,
                    "outstanding": Decimal(0),
                    "recovered": Decimal(0),
                    "payment_days": [],
                },
            )
            row["claim_count"] += 1
            row["denied_count"] += int(claim.status == "denied")
            row["outstanding"] += outstanding(
                claim.billed_amount or Decimal(0), claim.paid_amount or Decimal(0)
            )
        for payment, claim in payments:
            if claim.payer_id in grouped:
                grouped[claim.payer_id]["payment_days"].append(
                    max((payment.payment_date - claim.service_date).days, 0)
                )
        for recovery, claim in recoveries:
            if claim.payer_id in grouped:
                grouped[claim.payer_id]["recovered"] += recovery.recovered_amount
        return list(grouped.values())

    def denial_rows(self) -> list[tuple[Denial, Claim]]:
        return (
            self.db.query(Denial, Claim)
            .join(Claim, Denial.claim_id == Claim.id)
            .filter(
                Denial.organization_id == self.organization_id,
                Claim.organization_id == self.organization_id,
            )
            .order_by(Denial.claim_id, Denial.id.desc())
            .all()
        )

    def overpaid_claim_count(self) -> int:
        return (
            self.db.query(func.count(Claim.id))
            .filter(
                Claim.organization_id == self.organization_id,
                Claim.paid_amount > Claim.billed_amount,
            )
            .scalar()
            or 0
        )
