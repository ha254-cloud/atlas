from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from app.billing.models import RecoveryFeeSchedule
from app.billing.service import RecoveryFeeScheduleService
from app.models.claim import Claim
from app.models.recovery import Recovery
from app.models.recovery_attribution import (
    AttributionDisputeOutcome,
    AttributionStatus,
    PaymentEvidenceState,
    RecoveryAttributionDispute,
    RecoveryAttributionDisputeResolution,
    RecoveryAttributionVersion,
    RecoveryIntervention,
)
from app.models.submission import Submission
from app.payments.models import Payment
from app.recoveries.repository import RecoveryRepository
from app.recoveries.schemas import (
    RecoveryAttributionCreate,
    RecoveryAttributionDisputeResolutionCreate,
    RecoveryInterventionCreate,
)

_MONEY = Decimal("0.01")


@dataclass(frozen=True)
class DisputeResolutionResult:
    resolution: RecoveryAttributionDisputeResolution
    attribution: RecoveryAttributionVersion
    credit_note_id: int | None


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
        resolved_expected_amount = expected_amount or payment.expected_amount
        fee_percentage = fee_schedule.fee_percentage
        if amount <= 0:
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
        recovered_amount = (existing_amount + amount).quantize(
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
        actor_id: int,
        reason: str,
        correlation_id: str,
    ) -> Recovery:
        recovery = self.repository.for_payment_claim(payment.id, claim_id)
        if recovery is None:
            raise ValueError("Recovery projection not found for payment allocation")
        current = self.repository.latest_attribution(recovery.id)
        if current is not None and current.status == AttributionStatus.DISPUTED:
            raise ValueError(
                "Payment allocation cannot be adjusted while attribution is disputed"
            )

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
        if current is not None:
            eligible_amount = (
                min(current.eligible_amount, net_amount)
                if current.status == AttributionStatus.ELIGIBLE
                else Decimal("0.00")
            )
            self._append_attribution(
                recovery,
                status=AttributionStatus(current.status),
                intervention_id=current.intervention_id,
                confirmed_amount=net_amount,
                eligible_amount=eligible_amount,
                reversal_amount=self.repository.reversed_for_recovery(recovery),
                fee_schedule_id=current.fee_schedule_id,
                fee_percentage=current.fee_percentage,
                vat_percentage=current.vat_percentage,
                currency=current.currency,
                payment_terms_days=current.payment_terms_days,
                dispute_expires_at=current.dispute_expires_at,
                created_by=actor_id,
                reason=reason,
                correlation_id=correlation_id,
                previous=current,
            )
        self.db.flush()
        return recovery

    def verify(self, recovery_id: int, *, verified_by: int, reason: str) -> Recovery:
        recovery = self.repository.get_for_update(recovery_id)
        if recovery is None:
            raise ValueError(f"Recovery {recovery_id} not found")
        if not reason.strip():
            raise ValueError("Verification reason is required")
        if recovery.verified:
            if (
                recovery.verified_by == verified_by
                and recovery.verification_reason == reason.strip()
            ):
                return recovery
            raise ValueError("Recovery is already verified")
        recovery.verified = True
        recovery.verified_by = verified_by
        recovery.verified_at = datetime.now(UTC)
        recovery.verification_reason = reason.strip()
        self.db.flush()
        return recovery

    def record_intervention(
        self,
        payload: RecoveryInterventionCreate,
        *,
        actor_id: int,
        correlation_id: str,
    ) -> RecoveryIntervention:
        claim = self.db.query(Claim).filter(
            Claim.id == payload.claim_id,
            Claim.organization_id == self.organization_id,
        ).first()
        if claim is None:
            raise ValueError(f"Claim {payload.claim_id} not found")
        submission = None
        if payload.submission_id is not None:
            submission = self.db.query(Submission).filter(
                Submission.id == payload.submission_id,
                Submission.organization_id == self.organization_id,
                Submission.claim_id == claim.id,
            ).first()
            if submission is None:
                raise ValueError(f"Submission {payload.submission_id} not found")
            existing = self.repository.intervention_for_submission(
                submission.id,
                payload.intervention_type,
            )
            if existing is not None:
                if (
                    existing.claim_id == payload.claim_id
                    and self._as_utc(existing.occurred_at)
                    == self._as_utc(payload.occurred_at)
                    and existing.reason == payload.reason.strip()
                ):
                    return existing
                raise ValueError(
                    "Submission intervention conflicts with immutable evidence"
                )
        intervention = RecoveryIntervention(
            organization_id=self.organization_id,
            claim_id=claim.id,
            submission_id=submission.id if submission else None,
            intervention_type=payload.intervention_type,
            occurred_at=payload.occurred_at,
            actor_id=actor_id,
            reason=payload.reason.strip(),
            correlation_id=correlation_id,
        )
        self.db.add(intervention)
        self.db.flush()
        return intervention

    def interventions(self, recovery_id: int) -> list[RecoveryIntervention]:
        recovery = self.get(recovery_id)
        return self.repository.interventions_for_claim(recovery.claim_id)

    def decide_attribution(
        self,
        recovery_id: int,
        payload: RecoveryAttributionCreate,
        *,
        actor_id: int,
        correlation_id: str,
    ) -> RecoveryAttributionVersion:
        recovery = self.repository.get_for_update(recovery_id)
        if recovery is None:
            raise ValueError(f"Recovery {recovery_id} not found")
        if not recovery.verified:
            raise ValueError("Recovery must be verified before attribution")
        if recovery.verified_by == actor_id:
            raise ValueError(
                "Attribution approver must differ from the recovery verifier"
            )
        if self.repository.latest_attribution(recovery.id) is not None:
            raise ValueError(
                "Recovery already has an attribution decision; use the dispute workflow"
            )
        status = AttributionStatus(payload.status)
        intervention = self._validate_intervention(
            recovery,
            payload.intervention_id,
            required=status == AttributionStatus.ELIGIBLE,
        )
        self._require_cash_evidence(recovery)
        schedule = RecoveryFeeScheduleService(
            self.db,
            self.organization_id,
        ).effective_on(recovery.payment_date)
        confirmed_amount = self.repository.net_allocated_for_recovery(recovery)
        eligible_amount = (
            confirmed_amount
            if status == AttributionStatus.ELIGIBLE
            else Decimal("0.00")
        )
        return self._append_attribution(
            recovery,
            status=status,
            intervention_id=intervention.id if intervention else None,
            confirmed_amount=confirmed_amount,
            eligible_amount=eligible_amount,
            reversal_amount=self.repository.reversed_for_recovery(recovery),
            fee_schedule_id=schedule.id,
            fee_percentage=schedule.fee_percentage,
            vat_percentage=schedule.vat_percentage,
            currency=schedule.currency,
            payment_terms_days=schedule.payment_terms_days,
            dispute_expires_at=datetime.now(UTC)
            + timedelta(days=schedule.dispute_period_days),
            created_by=actor_id,
            reason=payload.reason,
            correlation_id=correlation_id,
        )

    def attributions(self, recovery_id: int) -> list[RecoveryAttributionVersion]:
        self.get(recovery_id)
        return self.repository.attributions_for_recovery(recovery_id)

    def open_dispute(
        self,
        recovery_id: int,
        *,
        actor_id: int,
        reason: str,
        correlation_id: str,
    ) -> RecoveryAttributionDispute:
        recovery = self.repository.get_for_update(recovery_id)
        if recovery is None:
            raise ValueError(f"Recovery {recovery_id} not found")
        current = self.repository.latest_attribution(recovery.id)
        if current is None:
            raise ValueError("Recovery has no attribution decision to dispute")
        if current.status == AttributionStatus.DISPUTED:
            raise ValueError("Recovery attribution is already disputed")
        if self.repository.unresolved_dispute(recovery.id) is not None:
            raise ValueError("Recovery attribution already has an unresolved dispute")
        if datetime.now(UTC) > self._as_utc(current.dispute_expires_at):
            raise ValueError("Attribution dispute period has expired")
        disputed = self._append_attribution(
            recovery,
            status=AttributionStatus.DISPUTED,
            intervention_id=current.intervention_id,
            confirmed_amount=current.confirmed_amount,
            eligible_amount=current.eligible_amount,
            reversal_amount=current.reversal_amount,
            fee_schedule_id=current.fee_schedule_id,
            fee_percentage=current.fee_percentage,
            vat_percentage=current.vat_percentage,
            currency=current.currency,
            payment_terms_days=current.payment_terms_days,
            dispute_expires_at=current.dispute_expires_at,
            created_by=actor_id,
            reason=reason,
            correlation_id=correlation_id,
            previous=current,
        )
        dispute = RecoveryAttributionDispute(
            organization_id=self.organization_id,
            recovery_id=recovery.id,
            attribution_version_id=disputed.id,
            opened_by=actor_id,
            reason=reason.strip(),
            correlation_id=correlation_id,
        )
        self.db.add(dispute)
        self.db.flush()
        return dispute

    def disputes(self, recovery_id: int) -> list[RecoveryAttributionDispute]:
        self.get(recovery_id)
        return self.repository.disputes_for_recovery(recovery_id)

    def resolve_dispute(
        self,
        recovery_id: int,
        dispute_id: int,
        payload: RecoveryAttributionDisputeResolutionCreate,
        *,
        actor_id: int,
        correlation_id: str,
    ) -> DisputeResolutionResult:
        recovery = self.repository.get_for_update(recovery_id)
        if recovery is None:
            raise ValueError(f"Recovery {recovery_id} not found")
        dispute = self.repository.get_dispute(dispute_id)
        if dispute is None or dispute.recovery_id != recovery.id:
            raise ValueError(f"Recovery attribution dispute {dispute_id} not found")
        if dispute.resolution is not None:
            raise ValueError("Recovery attribution dispute is already resolved")
        if dispute.opened_by == actor_id:
            raise ValueError("Dispute resolver must differ from the dispute opener")
        disputed = self.repository.attribution_by_id(dispute.attribution_version_id)
        if disputed is None:
            raise ValueError("Disputed attribution version not found")
        previous = self.repository.attribution_by_id(disputed.previous_version_id or 0)
        if previous is None:
            raise ValueError("Disputed attribution has no predecessor")
        eligible_amount = self._resolved_eligible_amount(
            payload,
            previous.eligible_amount,
            disputed.confirmed_amount,
        )
        resolution = RecoveryAttributionDisputeResolution(
            organization_id=self.organization_id,
            dispute_id=dispute.id,
            outcome=payload.outcome,
            eligible_amount=eligible_amount,
            resolved_by=actor_id,
            reason=payload.reason.strip(),
            correlation_id=correlation_id,
        )
        self.db.add(resolution)
        self.db.flush()
        attribution = self._append_attribution(
            recovery,
            status=(
                AttributionStatus.ELIGIBLE
                if eligible_amount > 0
                else AttributionStatus.INELIGIBLE
            ),
            intervention_id=disputed.intervention_id,
            confirmed_amount=disputed.confirmed_amount,
            eligible_amount=eligible_amount,
            reversal_amount=disputed.reversal_amount,
            fee_schedule_id=disputed.fee_schedule_id,
            fee_percentage=disputed.fee_percentage,
            vat_percentage=disputed.vat_percentage,
            currency=disputed.currency,
            payment_terms_days=disputed.payment_terms_days,
            dispute_expires_at=disputed.dispute_expires_at,
            created_by=actor_id,
            reason=payload.reason,
            correlation_id=correlation_id,
            previous=disputed,
        )
        # Resolution and any resulting invoice credit must commit atomically.
        from app.invoices.service import InvoiceService

        credit_note = InvoiceService(
            self.db,
            self.organization_id,
        ).create_credit_note_for_attribution_resolution(
            recovery=recovery,
            resolution=resolution,
            previous_eligible_amount=previous.eligible_amount,
            issued_by=actor_id,
            reason=payload.reason,
            correlation_id=correlation_id,
        )
        return DisputeResolutionResult(
            resolution=resolution,
            attribution=attribution,
            credit_note_id=credit_note.id if credit_note else None,
        )

    def get(self, recovery_id: int) -> Recovery:
        recovery = self.repository.get(recovery_id)
        if recovery is None:
            raise ValueError(f"Recovery {recovery_id} not found")
        return recovery

    def list(self) -> list[Recovery]:
        return self.repository.list()

    def _validate_intervention(
        self,
        recovery: Recovery,
        intervention_id: int | None,
        *,
        required: bool,
    ) -> RecoveryIntervention | None:
        if intervention_id is None:
            if required:
                raise ValueError("Eligible attribution requires intervention evidence")
            return None
        intervention = self.repository.get_intervention(intervention_id)
        if intervention is None or intervention.claim_id != recovery.claim_id:
            raise ValueError(f"Recovery intervention {intervention_id} not found")
        payment_cutoff = datetime.combine(
            recovery.payment_date,
            time.max,
            tzinfo=UTC,
        )
        if self._as_utc(intervention.occurred_at) > payment_cutoff:
            raise ValueError("Recovery intervention cannot occur after payment")
        return intervention

    @staticmethod
    def _require_cash_evidence(recovery: Recovery) -> None:
        if not recovery.payment.settlement_evidence:
            raise ValueError("Recovery has no settlement evidence")
        if recovery.payment.status.value not in {"paid", "partial"}:
            raise ValueError("Recovery payment is not cash-confirmed")

    def _append_attribution(
        self,
        recovery: Recovery,
        *,
        status: AttributionStatus,
        intervention_id: int | None,
        confirmed_amount: Decimal,
        eligible_amount: Decimal,
        reversal_amount: Decimal,
        fee_schedule_id: int,
        fee_percentage: Decimal,
        vat_percentage: Decimal,
        currency: str,
        payment_terms_days: int,
        dispute_expires_at: datetime,
        created_by: int,
        reason: str,
        correlation_id: str,
        previous: RecoveryAttributionVersion | None = None,
    ) -> RecoveryAttributionVersion:
        confirmed_amount = confirmed_amount.quantize(_MONEY, rounding=ROUND_HALF_UP)
        eligible_amount = eligible_amount.quantize(_MONEY, rounding=ROUND_HALF_UP)
        if eligible_amount < 0 or eligible_amount > confirmed_amount:
            raise ValueError("Eligible amount must be within the confirmed amount")
        attribution = RecoveryAttributionVersion(
            organization_id=self.organization_id,
            recovery_id=recovery.id,
            intervention_id=intervention_id,
            previous_version_id=previous.id if previous else None,
            version=(previous.version + 1 if previous else 1),
            status=status,
            evidence_state=PaymentEvidenceState.CASH_CONFIRMED,
            confirmed_amount=confirmed_amount,
            excluded_amount=(confirmed_amount - eligible_amount).quantize(_MONEY),
            reversal_amount=reversal_amount.quantize(_MONEY),
            eligible_amount=eligible_amount,
            fee_schedule_id=fee_schedule_id,
            fee_percentage=fee_percentage.quantize(_MONEY),
            vat_percentage=vat_percentage.quantize(_MONEY),
            currency=currency,
            payment_terms_days=payment_terms_days,
            dispute_expires_at=dispute_expires_at,
            created_by=created_by,
            reason=reason.strip(),
            correlation_id=correlation_id,
        )
        self.db.add(attribution)
        self.db.flush()
        return attribution

    @staticmethod
    def _resolved_eligible_amount(
        payload: RecoveryAttributionDisputeResolutionCreate,
        previous_eligible_amount: Decimal,
        confirmed_amount: Decimal,
    ) -> Decimal:
        if payload.outcome == AttributionDisputeOutcome.UPHELD:
            if payload.eligible_amount not in (None, previous_eligible_amount):
                raise ValueError(
                    "Upheld dispute must preserve the prior eligible amount"
                )
            return previous_eligible_amount.quantize(_MONEY)
        if payload.outcome == AttributionDisputeOutcome.ACCEPTED:
            if payload.eligible_amount not in (None, Decimal("0")):
                raise ValueError("Accepted dispute must have zero eligible amount")
            return Decimal("0.00")
        if payload.eligible_amount is None:
            raise ValueError("Partially upheld dispute requires eligible_amount")
        eligible_amount = payload.eligible_amount.quantize(_MONEY)
        if not Decimal("0") < eligible_amount < min(
            previous_eligible_amount,
            confirmed_amount,
        ):
            raise ValueError(
                "Partially upheld eligible amount must be positive and below "
                "the prior eligible amount"
            )
        return eligible_amount

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
