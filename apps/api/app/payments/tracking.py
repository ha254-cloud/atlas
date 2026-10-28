from datetime import UTC, date, datetime, time
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.appeal import Appeal, AppealStatus
from app.models.claim import Claim
from app.models.invoice import Invoice, InvoiceLine
from app.models.recovery import Recovery
from app.models.submission import Submission, SubmissionStatus
from app.payments.models import Payment, PaymentStatus
from app.payments.schemas import ClaimPaymentTrackingRead, PaymentTrackingStage

_SUBMITTED_STATUSES = {
    SubmissionStatus.SUBMITTED,
    SubmissionStatus.ACKNOWLEDGED,
    SubmissionStatus.IN_REVIEW,
    SubmissionStatus.UNDER_REVIEW,
    SubmissionStatus.ADDITIONAL_INFO_REQUIRED,
    SubmissionStatus.APPROVED,
    SubmissionStatus.ACCEPTED,
    SubmissionStatus.DENIED,
    SubmissionStatus.REJECTED,
    SubmissionStatus.PAID,
}
_RESPONSE_STATUSES = {
    SubmissionStatus.ACKNOWLEDGED,
    SubmissionStatus.IN_REVIEW,
    SubmissionStatus.UNDER_REVIEW,
    SubmissionStatus.ADDITIONAL_INFO_REQUIRED,
    SubmissionStatus.APPROVED,
    SubmissionStatus.ACCEPTED,
    SubmissionStatus.DENIED,
    SubmissionStatus.REJECTED,
    SubmissionStatus.PAID,
}
_FAILED_STATUSES = {
    SubmissionStatus.FAILED,
    SubmissionStatus.DENIED,
    SubmissionStatus.REJECTED,
}


def _as_datetime(value: date | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.combine(value, time.min, tzinfo=UTC)


class ClaimPaymentTrackingService:
    def __init__(self, db: Session, organization_id: int) -> None:
        self.db = db
        self.organization_id = organization_id

    def get(self, claim_id: int) -> ClaimPaymentTrackingRead:
        claim = (
            self.db.query(Claim)
            .filter(
                Claim.id == claim_id,
                Claim.organization_id == self.organization_id,
            )
            .first()
        )
        if claim is None:
            raise ValueError(f"Claim {claim_id} not found")

        appeal = (
            self.db.query(Appeal)
            .filter(
                Appeal.claim_id == claim_id,
                Appeal.organization_id == self.organization_id,
            )
            .order_by(Appeal.id.desc())
            .first()
        )
        submission = (
            self.db.query(Submission)
            .filter(
                Submission.claim_id == claim_id,
                Submission.organization_id == self.organization_id,
            )
            .order_by(Submission.id.desc())
            .first()
        )
        payments = (
            self.db.query(Payment)
            .filter(
                Payment.claim_id == claim_id,
                Payment.organization_id == self.organization_id,
                Payment.matched_at.isnot(None),
                Payment.status.in_([PaymentStatus.PAID, PaymentStatus.PARTIAL]),
            )
            .order_by(Payment.payment_date, Payment.id)
            .all()
        )
        recoveries = (
            self.db.query(Recovery)
            .filter(
                Recovery.claim_id == claim_id,
                Recovery.organization_id == self.organization_id,
                Recovery.verified.is_(True),
            )
            .order_by(Recovery.payment_date, Recovery.id)
            .all()
        )
        invoice_row = (
            self.db.query(Invoice, InvoiceLine)
            .join(
                InvoiceLine,
                InvoiceLine.invoice_id == Invoice.id,
            )
            .filter(
                Invoice.organization_id == self.organization_id,
                InvoiceLine.claim_id == claim_id,
            )
            .order_by(Invoice.id.desc())
            .first()
        )

        payment_currency = self._single_currency(payments)
        payment_amount = (
            sum((row.paid_amount for row in payments), Decimal(0))
            if payments and payment_currency
            else None
        )
        recovered_amount = (
            sum((row.recovered_amount for row in recoveries), Decimal(0)) if recoveries else None
        )
        atlas_fee_amount = (
            sum((row.atlas_fee_amount for row in recoveries), Decimal(0)) if recoveries else None
        )
        latest_payment = payments[-1] if payments else None
        latest_recovery = recoveries[-1] if recoveries else None
        invoice = invoice_row[0] if invoice_row else None

        appeal_submitted = bool(submission and submission.status in _SUBMITTED_STATUSES) or bool(
            appeal
            and appeal.status == AppealStatus.SUBMITTED
            and appeal.submitted_at
            and appeal.confirmation_number
        )
        response_received = bool(submission and submission.status in _RESPONSE_STATUSES)
        submission_failed = bool(submission and submission.status in _FAILED_STATUSES)
        payment_received = latest_payment is not None
        recovery_verified = latest_recovery is not None

        stages = self._stages(
            appeal_submitted=appeal_submitted,
            response_received=response_received,
            submission_failed=submission_failed,
            payment_received=payment_received,
            recovery_verified=recovery_verified,
            invoice_created=invoice is not None,
            appeal=appeal,
            submission=submission,
            latest_payment=latest_payment,
            latest_recovery=latest_recovery,
            invoice=invoice,
        )
        timestamps = [
            appeal.submitted_at if appeal else None,
            submission.updated_at if submission else None,
            latest_payment.updated_at if latest_payment else None,
            latest_recovery.updated_at if latest_recovery else None,
            invoice.updated_at if invoice else None,
        ]
        last_updated_at = max((value for value in timestamps if value), default=None)
        return ClaimPaymentTrackingRead(
            claim_id=claim_id,
            stages=stages,
            appeal_id=appeal.id if appeal else None,
            appeal_status=appeal.status.value if appeal else None,
            submission_id=submission.id if submission else None,
            submission_status=submission.status.value if submission else None,
            submission_channel=submission.connector if submission else None,
            payment_received=payment_received,
            payment_amount=payment_amount,
            payment_currency=payment_currency,
            payment_received_at=(
                _as_datetime(latest_payment.payment_date) if latest_payment else None
            ),
            recovery_verified=recovery_verified,
            recovered_amount=recovered_amount,
            atlas_fee_amount=atlas_fee_amount,
            recovery_verified_at=(latest_recovery.verified_at if latest_recovery else None),
            invoice_created=invoice is not None,
            invoice_id=invoice.id if invoice else None,
            invoice_number=invoice.invoice_number if invoice else None,
            invoice_status=invoice.status.value if invoice else None,
            last_updated_at=last_updated_at,
        )

    @staticmethod
    def _single_currency(payments: list[Payment]) -> str | None:
        currencies = {payment.currency for payment in payments}
        return next(iter(currencies)) if len(currencies) == 1 else None

    @staticmethod
    def _stages(
        *,
        appeal_submitted: bool,
        response_received: bool,
        submission_failed: bool,
        payment_received: bool,
        recovery_verified: bool,
        invoice_created: bool,
        appeal: Appeal | None,
        submission: Submission | None,
        latest_payment: Payment | None,
        latest_recovery: Recovery | None,
        invoice: Invoice | None,
    ) -> list[PaymentTrackingStage]:
        appeal_state = "complete" if appeal_submitted else ("current" if appeal else "pending")
        response_state = "pending"
        if submission_failed:
            response_state = "failed"
        elif response_received or payment_received:
            response_state = "complete"
        elif appeal_submitted:
            response_state = "current"
        payment_state = "complete" if payment_received else "pending"
        recovery_state = (
            "complete" if recovery_verified else ("current" if payment_received else "pending")
        )
        invoice_state = (
            "complete" if invoice_created else ("current" if recovery_verified else "pending")
        )
        return [
            PaymentTrackingStage(
                key="appeal_submitted",
                label=("Appeal submitted" if appeal_submitted else "Ready to submit"),
                state=appeal_state,
                detail=(
                    f"Recorded through {submission.connector}"
                    if submission and appeal_submitted
                    else "No verified submission record"
                ),
                occurred_at=appeal.submitted_at if appeal and appeal_submitted else None,
            ),
            PaymentTrackingStage(
                key="payer_response",
                label="Payer response",
                state=response_state,
                detail=submission.status.value.replace("_", " ") if submission else None,
                occurred_at=submission.completed_at if submission else None,
            ),
            PaymentTrackingStage(
                key="payment_received",
                label="Payment evidence matched",
                state=payment_state,
                detail=(
                    f"{latest_payment.source.value.replace('_', ' ')} evidence"
                    if latest_payment
                    else None
                ),
                occurred_at=(_as_datetime(latest_payment.payment_date) if latest_payment else None),
            ),
            PaymentTrackingStage(
                key="recovery_verified",
                label="Recovery verified",
                state=recovery_state,
                detail="Verified by finance" if recovery_verified else None,
                occurred_at=latest_recovery.verified_at if latest_recovery else None,
            ),
            PaymentTrackingStage(
                key="invoice_created",
                label="Invoice created",
                state=invoice_state,
                detail=invoice.invoice_number if invoice else None,
                occurred_at=invoice.created_at if invoice else None,
            ),
        ]
