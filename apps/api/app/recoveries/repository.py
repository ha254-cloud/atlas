from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.models.recovery import Recovery
from app.models.recovery_attribution import (
    RecoveryAttributionDispute,
    RecoveryAttributionVersion,
    RecoveryIntervention,
)
from app.payments.models import PaymentAllocation, PaymentAllocationType


class RecoveryRepository:
    def __init__(self, db: Session, organization_id: int) -> None:
        self.db = db
        self.organization_id = organization_id

    def get(self, recovery_id: int) -> Recovery | None:
        return self.db.query(Recovery).filter(
            Recovery.id == recovery_id,
            Recovery.organization_id == self.organization_id,
        ).first()

    def get_for_update(self, recovery_id: int) -> Recovery | None:
        return self.db.query(Recovery).filter(
            Recovery.id == recovery_id,
            Recovery.organization_id == self.organization_id,
        ).with_for_update().first()

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

    def get_intervention(self, intervention_id: int) -> RecoveryIntervention | None:
        return self.db.query(RecoveryIntervention).filter(
            RecoveryIntervention.id == intervention_id,
            RecoveryIntervention.organization_id == self.organization_id,
        ).first()

    def intervention_for_submission(
        self,
        submission_id: int,
        intervention_type: str,
    ) -> RecoveryIntervention | None:
        return self.db.query(RecoveryIntervention).filter(
            RecoveryIntervention.organization_id == self.organization_id,
            RecoveryIntervention.submission_id == submission_id,
            RecoveryIntervention.intervention_type == intervention_type,
        ).first()

    def interventions_for_claim(self, claim_id: int) -> list[RecoveryIntervention]:
        return self.db.query(RecoveryIntervention).filter(
            RecoveryIntervention.organization_id == self.organization_id,
            RecoveryIntervention.claim_id == claim_id,
        ).order_by(
            RecoveryIntervention.occurred_at,
            RecoveryIntervention.id,
        ).all()

    def attribution_by_id(
        self,
        attribution_id: int,
    ) -> RecoveryAttributionVersion | None:
        return self.db.query(RecoveryAttributionVersion).filter(
            RecoveryAttributionVersion.id == attribution_id,
            RecoveryAttributionVersion.organization_id == self.organization_id,
        ).first()

    def latest_attribution(
        self,
        recovery_id: int,
    ) -> RecoveryAttributionVersion | None:
        return self.db.query(RecoveryAttributionVersion).filter(
            RecoveryAttributionVersion.organization_id == self.organization_id,
            RecoveryAttributionVersion.recovery_id == recovery_id,
        ).order_by(RecoveryAttributionVersion.version.desc()).first()

    def attributions_for_recovery(
        self,
        recovery_id: int,
    ) -> list[RecoveryAttributionVersion]:
        return self.db.query(RecoveryAttributionVersion).filter(
            RecoveryAttributionVersion.organization_id == self.organization_id,
            RecoveryAttributionVersion.recovery_id == recovery_id,
        ).order_by(RecoveryAttributionVersion.version).all()

    def get_dispute(
        self,
        dispute_id: int,
    ) -> RecoveryAttributionDispute | None:
        return self.db.query(RecoveryAttributionDispute).filter(
            RecoveryAttributionDispute.id == dispute_id,
            RecoveryAttributionDispute.organization_id == self.organization_id,
        ).first()

    def unresolved_dispute(
        self,
        recovery_id: int,
    ) -> RecoveryAttributionDispute | None:
        return self.db.query(RecoveryAttributionDispute).filter(
            RecoveryAttributionDispute.organization_id == self.organization_id,
            RecoveryAttributionDispute.recovery_id == recovery_id,
            ~RecoveryAttributionDispute.resolution.has(),
        ).first()

    def disputes_for_recovery(
        self,
        recovery_id: int,
    ) -> list[RecoveryAttributionDispute]:
        return self.db.query(RecoveryAttributionDispute).filter(
            RecoveryAttributionDispute.organization_id == self.organization_id,
            RecoveryAttributionDispute.recovery_id == recovery_id,
        ).order_by(RecoveryAttributionDispute.opened_at).all()

    def net_allocated_for_recovery(self, recovery: Recovery) -> Decimal:
        amount = self.db.query(
            func.coalesce(
                func.sum(
                    case(
                        (
                            PaymentAllocation.allocation_type
                            == PaymentAllocationType.ALLOCATION,
                            PaymentAllocation.amount,
                        ),
                        else_=-PaymentAllocation.amount,
                    )
                ),
                0,
            )
        ).filter(
            PaymentAllocation.organization_id == self.organization_id,
            PaymentAllocation.payment_id == recovery.payment_id,
            PaymentAllocation.claim_id == recovery.claim_id,
        ).scalar()
        return Decimal(amount).quantize(Decimal("0.01"))

    def reversed_for_recovery(self, recovery: Recovery) -> Decimal:
        amount = self.db.query(
            func.coalesce(func.sum(PaymentAllocation.amount), 0)
        ).filter(
            PaymentAllocation.organization_id == self.organization_id,
            PaymentAllocation.payment_id == recovery.payment_id,
            PaymentAllocation.claim_id == recovery.claim_id,
            PaymentAllocation.allocation_type != PaymentAllocationType.ALLOCATION,
        ).scalar()
        return Decimal(amount).quantize(Decimal("0.01"))

    def verified_uninvoiced(self, period_start: date, period_end: date) -> list[Recovery]:
        return self.db.query(Recovery).filter(
            Recovery.organization_id == self.organization_id,
            Recovery.verified.is_(True),
            Recovery.payment_date >= period_start,
            Recovery.payment_date <= period_end,
            ~Recovery.invoice_line.has(),
        ).order_by(Recovery.payment_date, Recovery.id).all()

    def attributable_uninvoiced(
        self,
        period_start: date,
        period_end: date,
    ) -> list[tuple[Recovery, RecoveryAttributionVersion]]:
        latest = self.db.query(
            RecoveryAttributionVersion.recovery_id.label("recovery_id"),
            func.max(RecoveryAttributionVersion.version).label("version"),
        ).filter(
            RecoveryAttributionVersion.organization_id == self.organization_id
        ).group_by(
            RecoveryAttributionVersion.recovery_id
        ).subquery()
        return self.db.query(Recovery, RecoveryAttributionVersion).join(
            latest,
            latest.c.recovery_id == Recovery.id,
        ).join(
            RecoveryAttributionVersion,
            (
                (RecoveryAttributionVersion.recovery_id == latest.c.recovery_id)
                & (RecoveryAttributionVersion.version == latest.c.version)
            ),
        ).filter(
            Recovery.organization_id == self.organization_id,
            Recovery.verified.is_(True),
            Recovery.payment_date >= period_start,
            Recovery.payment_date <= period_end,
            RecoveryAttributionVersion.status == "eligible",
            RecoveryAttributionVersion.eligible_amount > 0,
            ~Recovery.invoice_line.has(),
        ).order_by(Recovery.payment_date, Recovery.id).all()
