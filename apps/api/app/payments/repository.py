from __future__ import annotations

from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.claim import Claim
from app.models.payer import Payer
from app.payments.models import (
    Payment,
    PaymentAllocation,
    PaymentAllocationType,
    PaymentSettlementEvidence,
    PaymentSource,
)


class PaymentRepository:
    def __init__(self, db: Session, organization_id: int) -> None:
        self.db = db
        self.organization_id = organization_id

    def get(self, payment_id: int) -> Payment | None:
        return self.db.query(Payment).filter(
            Payment.id == payment_id,
            Payment.organization_id == self.organization_id,
        ).first()

    def get_for_update(self, payment_id: int) -> Payment | None:
        return (
            self.db.query(Payment)
            .filter(
                Payment.id == payment_id,
                Payment.organization_id == self.organization_id,
            )
            .with_for_update()
            .first()
        )

    def by_reference(
        self,
        source: PaymentSource,
        payment_reference: str,
    ) -> Payment | None:
        return self.db.query(Payment).filter(
            Payment.organization_id == self.organization_id,
            Payment.source == source,
            Payment.payment_reference == payment_reference,
        ).first()

    def list(self) -> list[Payment]:
        return self.db.query(Payment).filter(
            Payment.organization_id == self.organization_id
        ).order_by(Payment.payment_date.desc(), Payment.id.desc()).all()

    def settlement_evidence_for_payment(
        self,
        payment_id: int,
    ) -> list[PaymentSettlementEvidence]:
        return (
            self.db.query(PaymentSettlementEvidence)
            .filter(
                PaymentSettlementEvidence.organization_id == self.organization_id,
                PaymentSettlementEvidence.payment_id == payment_id,
            )
            .order_by(PaymentSettlementEvidence.id)
            .all()
        )

    def settlement_evidence_by_key(
        self,
        idempotency_key: str,
    ) -> PaymentSettlementEvidence | None:
        return (
            self.db.query(PaymentSettlementEvidence)
            .filter(
                PaymentSettlementEvidence.organization_id == self.organization_id,
                PaymentSettlementEvidence.idempotency_key == idempotency_key,
            )
            .first()
        )

    def get_allocation(self, allocation_id: int) -> PaymentAllocation | None:
        return (
            self.db.query(PaymentAllocation)
            .filter(
                PaymentAllocation.id == allocation_id,
                PaymentAllocation.organization_id == self.organization_id,
            )
            .first()
        )

    def get_allocation_for_update(
        self,
        allocation_id: int,
    ) -> PaymentAllocation | None:
        return (
            self.db.query(PaymentAllocation)
            .filter(
                PaymentAllocation.id == allocation_id,
                PaymentAllocation.organization_id == self.organization_id,
            )
            .with_for_update()
            .first()
        )

    def claims_for_update(self, claim_ids: set[int]) -> dict[int, Claim]:
        if not claim_ids:
            return {}
        rows = (
            self.db.query(Claim)
            .filter(
                Claim.organization_id == self.organization_id,
                Claim.id.in_(sorted(claim_ids)),
            )
            .order_by(Claim.id)
            .with_for_update()
            .all()
        )
        return {row.id: row for row in rows}

    def lock_idempotency_key(self, idempotency_key: str) -> None:
        if self.db.get_bind().dialect.name != "postgresql":
            return
        self.db.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:lock_key, 0))"),
            {
                "lock_key": (
                    f"payment-ledger:{self.organization_id}:{idempotency_key}"
                )
            },
        )

    def allocation_by_key(self, idempotency_key: str) -> PaymentAllocation | None:
        return (
            self.db.query(PaymentAllocation)
            .filter(
                PaymentAllocation.organization_id == self.organization_id,
                PaymentAllocation.idempotency_key == idempotency_key,
            )
            .first()
        )

    def allocations_for_payment(self, payment_id: int) -> list[PaymentAllocation]:
        return (
            self.db.query(PaymentAllocation)
            .filter(
                PaymentAllocation.organization_id == self.organization_id,
                PaymentAllocation.payment_id == payment_id,
            )
            .order_by(PaymentAllocation.id)
            .all()
        )

    def net_allocated_amount(self, payment_id: int) -> Decimal:
        rows = self.allocations_for_payment(payment_id)
        return sum(
            (
                row.amount
                if row.allocation_type == PaymentAllocationType.ALLOCATION
                else -row.amount
                for row in rows
            ),
            Decimal("0"),
        )

    def original_allocated_amount(self, payment_id: int) -> Decimal:
        return sum(
            (
                row.amount
                for row in self.allocations_for_payment(payment_id)
                if row.allocation_type == PaymentAllocationType.ALLOCATION
            ),
            Decimal("0"),
        )

    def allocatable_amount(self, payment: Payment) -> Decimal:
        return max(
            payment.paid_amount - self.original_allocated_amount(payment.id),
            Decimal("0"),
        )

    def net_allocated_for_claim(self, payment_id: int, claim_id: int) -> Decimal:
        rows = [
            row
            for row in self.allocations_for_payment(payment_id)
            if row.claim_id == claim_id
        ]
        return sum(
            (
                row.amount
                if row.allocation_type == PaymentAllocationType.ALLOCATION
                else -row.amount
                for row in rows
            ),
            Decimal("0"),
        )

    def adjusted_amount(self, allocation_id: int) -> Decimal:
        return sum(
            (
                row.amount
                for row in self.db.query(PaymentAllocation)
                .filter(
                    PaymentAllocation.organization_id == self.organization_id,
                    PaymentAllocation.parent_allocation_id == allocation_id,
                )
                .all()
            ),
            Decimal("0"),
        )

    def claim_candidates(self, *, currency: str) -> list[tuple[Claim, Payer]]:
        return (
            self.db.query(Claim, Payer)
            .join(Payer, Payer.id == Claim.payer_id)
            .filter(
                Claim.organization_id == self.organization_id,
                Payer.organization_id == self.organization_id,
                Claim.currency == currency,
                Claim.billed_amount > Claim.paid_amount,
            )
            .order_by(Claim.service_date.desc(), Claim.id.desc())
            .all()
        )
