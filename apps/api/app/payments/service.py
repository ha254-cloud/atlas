import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy.orm import Session

from app.billing.service import RecoveryFeeScheduleService
from app.models.claim import Claim
from app.models.submission import Submission
from app.payments.models import Payment, PaymentStatus
from app.payments.repository import PaymentRepository
from app.payments.schemas import PaymentIngest, PaymentMatchCandidate
from app.recoveries.service import RecoveryAttributionService

_MONEY = Decimal("0.01")


@dataclass(frozen=True)
class PaymentIngestResult:
    payment: Payment
    created: bool


class PaymentService:
    def __init__(self, db: Session, organization_id: int) -> None:
        self.db = db
        self.organization_id = organization_id
        self.repository = PaymentRepository(db, organization_id)

    def ingest(
        self,
        payload: PaymentIngest,
        *,
        correlation_id: str | None = None,
        actor_id: int | None = None,
    ) -> PaymentIngestResult:
        existing = self.repository.by_reference(
            payload.source,
            payload.payment_reference,
        )
        if existing is not None:
            self._validate_idempotent_replay(existing, payload)
            return PaymentIngestResult(payment=existing, created=False)

        claim, submission = self._resolve_match(
            payload.claim_id,
            payload.submission_id,
        )
        if claim is not None and claim.currency != payload.currency:
            raise ValueError(
                f"Claim currency {claim.currency} does not match payment currency "
                f"{payload.currency}"
            )
        payment = Payment(
            organization_id=self.organization_id,
            claim_id=claim.id if claim else None,
            submission_id=submission.id if submission else None,
            payer_name=payload.payer_name.strip(),
            payment_reference=payload.payment_reference.strip(),
            payment_date=payload.payment_date,
            expected_amount=payload.expected_amount.quantize(_MONEY),
            paid_amount=payload.paid_amount.quantize(_MONEY),
            adjustment_amount=payload.adjustment_amount.quantize(_MONEY),
            currency=payload.currency,
            payment_method=payload.payment_method,
            status=payload.status,
            source=payload.source,
            raw_payload=payload.raw_payload,
            matched_at=datetime.utcnow() if claim else None,
            matched_by_id=actor_id if claim else None,
            matching_method="source_claim_id" if claim else None,
            matching_reason=(
                "Claim supplied with payment evidence" if claim else None
            ),
            correlation_id=correlation_id or str(uuid4()),
        )
        self.db.add(payment)
        self.db.flush()
        if claim is not None and self._is_recoverable(payment):
            self._create_recovery(payment, claim)
        return PaymentIngestResult(payment=payment, created=True)

    def match(
        self,
        payment_id: int,
        *,
        claim_id: int,
        submission_id: int | None = None,
        matched_by: int,
        reason: str,
    ) -> Payment:
        payment = self.get(payment_id)
        if payment.claim_id is not None:
            if (
                payment.claim_id == claim_id
                and payment.submission_id == submission_id
                and payment.matching_reason == reason.strip()
            ):
                return payment
            raise ValueError("Payment is already matched and cannot be rematched")
        if not reason.strip():
            raise ValueError("Matching reason is required")
        claim, submission = self._resolve_match(claim_id, submission_id)
        if claim is None:
            raise ValueError("claim_id is required")
        if claim.currency != payment.currency:
            raise ValueError(
                f"Claim currency {claim.currency} does not match payment currency "
                f"{payment.currency}"
            )
        payment.claim_id = claim.id
        payment.submission_id = submission.id if submission else None
        payment.matched_at = datetime.utcnow()
        payment.matched_by_id = matched_by
        payment.matching_method = "manual"
        payment.matching_reason = reason.strip()
        if self._is_recoverable(payment):
            self._create_recovery(payment, claim)
        self.db.flush()
        return payment

    def candidates(self, payment_id: int) -> list[PaymentMatchCandidate]:
        payment = self.get(payment_id)
        if payment.claim_id is not None:
            return []

        payload_text = json.dumps(
            payment.raw_payload,
            sort_keys=True,
            default=str,
        ).casefold()
        payment_payer = self._normalize(payment.payer_name)
        candidates: list[PaymentMatchCandidate] = []
        for claim, payer in self.repository.claim_candidates(currency=payment.currency):
            outstanding = max(
                (claim.billed_amount or Decimal("0"))
                - (claim.paid_amount or Decimal("0")),
                Decimal("0"),
            ).quantize(_MONEY)
            reasons: list[str] = ["currency_match"]
            confidence = 10

            if claim.claim_number.casefold() in payload_text:
                reasons.append("claim_reference")
                confidence += 50
            if self._normalize(payer.name) == payment_payer:
                reasons.append("payer_name")
                confidence += 25
            if payment.paid_amount == outstanding:
                reasons.append("exact_outstanding_amount")
                confidence += 15
            elif payment.paid_amount <= outstanding:
                reasons.append("amount_within_outstanding")
                confidence += 5

            if confidence < 30:
                continue
            candidates.append(
                PaymentMatchCandidate(
                    claim_id=claim.id,
                    claim_number=claim.claim_number,
                    payer_name=payer.name,
                    billed_amount=claim.billed_amount,
                    paid_amount=claim.paid_amount or Decimal("0"),
                    outstanding_amount=outstanding,
                    currency=claim.currency,
                    confidence=min(confidence, 100),
                    reasons=reasons,
                )
            )
        return sorted(
            candidates,
            key=lambda candidate: (-candidate.confidence, candidate.claim_id),
        )[:10]

    def get(self, payment_id: int) -> Payment:
        payment = self.repository.get(payment_id)
        if payment is None:
            raise ValueError(f"Payment {payment_id} not found")
        return payment

    def list(self) -> list[Payment]:
        return self.repository.list()

    def _resolve_match(
        self,
        claim_id: int | None,
        submission_id: int | None,
    ) -> tuple[Claim | None, Submission | None]:
        submission = None
        if submission_id is not None:
            submission = self.db.query(Submission).filter(
                Submission.id == submission_id,
                Submission.organization_id == self.organization_id,
            ).first()
            if submission is None:
                raise ValueError(f"Submission {submission_id} not found")
            if claim_id is not None and submission.claim_id != claim_id:
                raise ValueError("Submission does not belong to the supplied claim")
            claim_id = submission.claim_id

        claim = None
        if claim_id is not None:
            claim = self.db.query(Claim).filter(
                Claim.id == claim_id,
                Claim.organization_id == self.organization_id,
            ).first()
            if claim is None:
                raise ValueError(f"Claim {claim_id} not found")
        return claim, submission

    def _create_recovery(self, payment: Payment, claim: Claim) -> None:
        schedule = RecoveryFeeScheduleService(
            self.db,
            self.organization_id,
        ).effective_on(payment.payment_date)
        RecoveryAttributionService(
            self.db,
            self.organization_id,
        ).record_payment(payment, fee_schedule=schedule)
        claim.paid_amount = (claim.paid_amount or Decimal("0")) + payment.paid_amount

    @staticmethod
    def _is_recoverable(payment: Payment) -> bool:
        return payment.paid_amount > 0 and payment.status in {
            PaymentStatus.PAID,
            PaymentStatus.PARTIAL,
        }

    @staticmethod
    def _validate_idempotent_replay(
        existing: Payment,
        payload: PaymentIngest,
    ) -> None:
        immutable_values = {
            "claim_id": payload.claim_id,
            "submission_id": payload.submission_id,
            "payment_date": payload.payment_date,
            "expected_amount": payload.expected_amount.quantize(_MONEY),
            "paid_amount": payload.paid_amount.quantize(_MONEY),
            "adjustment_amount": payload.adjustment_amount.quantize(_MONEY),
            "currency": payload.currency,
            "status": payload.status,
            "raw_payload": payload.raw_payload,
        }
        conflicts = [
            field
            for field, expected in immutable_values.items()
            if getattr(existing, field) != expected
        ]
        if conflicts:
            raise ValueError(
                "Payment reference conflicts with immutable fields: "
                + ", ".join(conflicts)
            )

    @staticmethod
    def _normalize(value: str) -> str:
        return " ".join(value.casefold().split())
