from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256
from uuid import uuid4

from sqlalchemy.orm import Session

from app.billing.service import RecoveryFeeScheduleService
from app.invoices.service import InvoiceService
from app.models.claim import Claim
from app.models.submission import Submission
from app.payments.models import (
    LEGACY_PAYMENT_TERMS_DAYS,
    Payment,
    PaymentAllocation,
    PaymentAllocationType,
    PaymentSettlementEvidence,
    PaymentStatus,
)
from app.payments.repository import PaymentRepository
from app.payments.schemas import (
    PaymentAllocationAdjustmentCreate,
    PaymentAllocationBatchCreate,
    PaymentIngest,
    PaymentMatchCandidate,
    SettlementEvidenceCreate,
)
from app.recoveries.service import RecoveryAttributionService

_MONEY = Decimal("0.01")


@dataclass(frozen=True)
class PaymentIngestResult:
    payment: Payment
    created: bool


@dataclass(frozen=True)
class PaymentAllocationBatchResult:
    allocations: list[PaymentAllocation]
    created: bool
    allocated_amount: Decimal
    unallocated_amount: Decimal


@dataclass(frozen=True)
class PaymentAdjustmentResult:
    allocation: PaymentAllocation
    created: bool
    credit_note_id: int | None


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
        fee_schedule = RecoveryFeeScheduleService(
            self.db,
            self.organization_id,
        ).repository.effective_on(payload.payment_date)
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
            payment_terms_days=(
                fee_schedule.payment_terms_days
                if fee_schedule is not None
                else LEGACY_PAYMENT_TERMS_DAYS
            ),
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
        self._record_source_evidence(payment, payload, actor_id=actor_id)
        if claim is not None and self._is_recoverable(payment):
            self.allocate(
                payment.id,
                PaymentAllocationBatchCreate(
                    allocations=[
                        {
                            "claim_id": claim.id,
                            "submission_id": submission.id if submission else None,
                            "amount": payment.paid_amount,
                        }
                    ],
                    reason="Claim supplied with payment evidence",
                    idempotency_key=f"ingest-payment-{payment.id}",
                ),
                actor_id=actor_id,
                actor_type="user" if actor_id else "system",
                correlation_id=payment.correlation_id,
            )
        return PaymentIngestResult(payment=payment, created=True)

    def match(
        self,
        payment_id: int,
        *,
        claim_id: int,
        submission_id: int | None = None,
        matched_by: int,
        reason: str,
        correlation_id: str | None = None,
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
            self.allocate(
                payment.id,
                PaymentAllocationBatchCreate(
                    allocations=[
                        {
                            "claim_id": claim.id,
                            "submission_id": submission.id if submission else None,
                            "amount": payment.paid_amount,
                        }
                    ],
                    reason=reason,
                    idempotency_key=f"match-payment-{payment.id}",
                ),
                actor_id=matched_by,
                actor_type="user",
                correlation_id=correlation_id or payment.correlation_id,
            )
            payment.matching_method = "manual"
        self.db.flush()
        return payment

    def record_settlement_evidence(
        self,
        payment_id: int,
        payload: SettlementEvidenceCreate,
        *,
        actor_id: int,
        correlation_id: str,
    ) -> tuple[PaymentSettlementEvidence, bool]:
        payment = self._get_for_update(payment_id)
        self.repository.lock_idempotency_key(payload.idempotency_key)
        existing = self.repository.settlement_evidence_by_key(
            payload.idempotency_key
        )
        if existing is not None:
            expected = {
                "payment_id": payment.id,
                "evidence_type": payload.evidence_type,
                "settlement_reference": payload.settlement_reference.strip(),
                "amount": payload.amount.quantize(_MONEY),
                "currency": payload.currency,
                "source_hash": payload.source_hash.lower(),
                "reason": payload.reason.strip(),
            }
            received_at_matches = self._as_utc(existing.received_at) == self._as_utc(
                payload.received_at
            )
            if (
                not received_at_matches
                or any(getattr(existing, key) != value for key, value in expected.items())
            ):
                raise ValueError("Idempotency key conflicts with settlement evidence")
            return existing, False
        if payload.currency != payment.currency:
            raise ValueError("Settlement evidence currency does not match payment")
        if payload.amount != payment.paid_amount:
            raise ValueError("Settlement evidence amount must equal the payment amount")
        evidence = PaymentSettlementEvidence(
            organization_id=self.organization_id,
            payment_id=payment.id,
            evidence_type=payload.evidence_type,
            settlement_reference=payload.settlement_reference.strip(),
            amount=payload.amount.quantize(_MONEY),
            currency=payload.currency,
            received_at=payload.received_at,
            source_hash=payload.source_hash.lower(),
            actor_id=actor_id,
            reason=payload.reason.strip(),
            correlation_id=correlation_id,
            idempotency_key=payload.idempotency_key,
        )
        self.db.add(evidence)
        self.db.flush()
        return evidence, True

    def settlement_evidence(
        self,
        payment_id: int,
    ) -> list[PaymentSettlementEvidence]:
        self.get(payment_id)
        return self.repository.settlement_evidence_for_payment(payment_id)

    def allocate(
        self,
        payment_id: int,
        payload: PaymentAllocationBatchCreate,
        *,
        actor_id: int | None,
        actor_type: str,
        correlation_id: str,
    ) -> PaymentAllocationBatchResult:
        payment = self._get_for_update(payment_id)
        if not self._is_recoverable(payment):
            raise ValueError("Only paid or partial positive payments can be allocated")
        if not self.repository.settlement_evidence_for_payment(payment.id):
            self._ensure_source_evidence(
                payment,
                actor_id=actor_id,
                correlation_id=correlation_id,
            )

        keys = [
            f"{payload.idempotency_key}:{index}"
            for index in range(len(payload.allocations))
        ]
        for key in keys:
            self.repository.lock_idempotency_key(key)
        existing = [
            self.repository.allocation_by_key(key)
            for key in keys
        ]
        if any(existing):
            if not all(existing):
                raise ValueError("Allocation batch is incomplete and requires support review")
            rows = [row for row in existing if row is not None]
            self._validate_allocation_replay(payment, payload, rows)
            allocated = self.repository.net_allocated_amount(payment.id)
            return PaymentAllocationBatchResult(
                allocations=rows,
                created=False,
                allocated_amount=allocated,
                unallocated_amount=self.repository.allocatable_amount(payment),
            )

        locked_claims = self.repository.claims_for_update(
            {item.claim_id for item in payload.allocations}
        )
        requested = sum(
            (item.amount for item in payload.allocations),
            Decimal("0"),
        ).quantize(_MONEY)

        resolved: list[tuple[Claim, Submission | None]] = []
        per_claim: dict[int, Decimal] = {}
        for item in payload.allocations:
            claim, submission = self._resolve_match(
                item.claim_id,
                item.submission_id,
            )
            if claim is None:
                raise ValueError("claim_id is required")
            if claim.id not in locked_claims:
                raise ValueError(f"Claim {claim.id} not found")
            if claim.currency != payment.currency:
                raise ValueError(
                    f"Claim currency {claim.currency} does not match payment currency "
                    f"{payment.currency}"
                )
            outstanding = max(
                claim.billed_amount - (claim.paid_amount or Decimal("0")),
                Decimal("0"),
            )
            cumulative = per_claim.get(claim.id, Decimal("0")) + item.amount
            if cumulative > outstanding:
                raise ValueError(
                    f"Allocation exceeds outstanding amount for claim {claim.id}"
                )
            per_claim[claim.id] = cumulative
            resolved.append((claim, submission))

        available = self.repository.allocatable_amount(payment)
        if requested > available:
            raise ValueError("Allocation batch exceeds the unallocated payment amount")

        allocations: list[PaymentAllocation] = []
        for index, (item, (claim, submission)) in enumerate(
            zip(payload.allocations, resolved, strict=True)
        ):
            allocation = PaymentAllocation(
                organization_id=self.organization_id,
                payment_id=payment.id,
                claim_id=claim.id,
                submission_id=submission.id if submission else None,
                allocation_type=PaymentAllocationType.ALLOCATION,
                amount=item.amount.quantize(_MONEY),
                currency=payment.currency,
                actor_id=actor_id,
                actor_type=actor_type,
                reason=payload.reason.strip(),
                correlation_id=correlation_id,
                idempotency_key=keys[index],
                item_index=index,
            )
            self.db.add(allocation)
            self.db.flush()
            schedule = RecoveryFeeScheduleService(
                self.db,
                self.organization_id,
            ).effective_on(payment.payment_date)
            payment.payment_terms_days = schedule.payment_terms_days
            RecoveryAttributionService(
                self.db,
                self.organization_id,
            ).record_allocation(
                payment,
                amount=allocation.amount,
                fee_schedule=schedule,
                claim_id=claim.id,
                submission_id=submission.id if submission else None,
                expected_amount=claim.billed_amount,
            )
            claim.paid_amount = (claim.paid_amount or Decimal("0")) + allocation.amount
            allocations.append(allocation)

        payment.matched_at = payment.matched_at or datetime.now(UTC)
        payment.matched_by_id = actor_id
        payment.matching_method = (
            "bulk_allocation" if len(allocations) > 1 else "manual_allocation"
        )
        payment.matching_reason = payload.reason.strip()
        original_allocations = [
            row
            for row in self.repository.allocations_for_payment(payment.id)
            if row.allocation_type == PaymentAllocationType.ALLOCATION
        ]
        claim_ids = {row.claim_id for row in original_allocations}
        if len(claim_ids) == 1:
            payment.claim_id = next(iter(claim_ids))
            submission_ids = {row.submission_id for row in original_allocations}
            payment.submission_id = (
                next(iter(submission_ids)) if len(submission_ids) == 1 else None
            )
        else:
            payment.claim_id = None
            payment.submission_id = None
        self.db.flush()
        allocated = self.repository.net_allocated_amount(payment.id)
        return PaymentAllocationBatchResult(
            allocations=allocations,
            created=True,
            allocated_amount=allocated,
            unallocated_amount=self.repository.allocatable_amount(payment),
        )

    def adjust_allocation(
        self,
        allocation_id: int,
        payload: PaymentAllocationAdjustmentCreate,
        *,
        actor_id: int,
        correlation_id: str,
    ) -> PaymentAdjustmentResult:
        allocation_probe = self.repository.get_allocation(allocation_id)
        if allocation_probe is None:
            raise ValueError(f"Payment allocation {allocation_id} not found")
        payment = self._get_for_update(allocation_probe.payment_id)
        self.repository.lock_idempotency_key(payload.idempotency_key)
        original = self.repository.get_allocation_for_update(allocation_id)
        if original is None:
            raise ValueError(f"Payment allocation {allocation_id} not found")
        if original.allocation_type != PaymentAllocationType.ALLOCATION:
            raise ValueError("Only original allocations can be adjusted")

        existing = self.repository.allocation_by_key(payload.idempotency_key)
        if existing is not None:
            if (
                existing.parent_allocation_id != original.id
                or existing.allocation_type != payload.adjustment_type
                or existing.amount != payload.amount.quantize(_MONEY)
                or existing.reason != payload.reason.strip()
            ):
                raise ValueError("Idempotency key conflicts with allocation adjustment")
            credit_note = InvoiceService(
                self.db,
                self.organization_id,
            ).repository.credit_note_for_allocation(existing.id)
            return PaymentAdjustmentResult(
                allocation=existing,
                created=False,
                credit_note_id=credit_note.id if credit_note else None,
            )

        locked_claims = self.repository.claims_for_update({original.claim_id})
        claim = locked_claims.get(original.claim_id)
        if claim is None:
            raise ValueError(f"Claim {original.claim_id} not found")
        remaining = original.amount - self.repository.adjusted_amount(original.id)
        if payload.amount > remaining:
            raise ValueError("Adjustment exceeds the remaining allocated amount")
        adjustment = PaymentAllocation(
            organization_id=self.organization_id,
            payment_id=original.payment_id,
            claim_id=original.claim_id,
            submission_id=original.submission_id,
            parent_allocation_id=original.id,
            allocation_type=payload.adjustment_type,
            amount=payload.amount.quantize(_MONEY),
            currency=original.currency,
            actor_id=actor_id,
            actor_type="user",
            reason=payload.reason.strip(),
            correlation_id=correlation_id,
            idempotency_key=payload.idempotency_key,
            item_index=0,
        )
        self.db.add(adjustment)
        self.db.flush()

        claim.paid_amount = max(
            (claim.paid_amount or Decimal("0")) - adjustment.amount,
            Decimal("0"),
        )
        net_amount = self.repository.net_allocated_for_claim(
            payment.id,
            claim.id,
        )
        recovery = RecoveryAttributionService(
            self.db,
            self.organization_id,
        ).apply_adjustment(
            payment=payment,
            claim_id=claim.id,
            net_amount=net_amount,
        )
        credit_note = InvoiceService(
            self.db,
            self.organization_id,
        ).create_credit_note_for_adjustment(
            recovery=recovery,
            allocation=adjustment,
            issued_by=actor_id,
            reason=payload.reason,
            correlation_id=correlation_id,
        )
        self.db.flush()
        return PaymentAdjustmentResult(
            allocation=adjustment,
            created=True,
            credit_note_id=credit_note.id if credit_note else None,
        )

    def candidates(self, payment_id: int) -> list[PaymentMatchCandidate]:
        payment = self.get(payment_id)
        unallocated_amount = self.repository.allocatable_amount(payment).quantize(
            _MONEY
        )
        if unallocated_amount <= 0:
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
            if unallocated_amount == outstanding:
                reasons.append("exact_outstanding_amount")
                confidence += 15
            elif unallocated_amount <= outstanding:
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

    def _get_for_update(self, payment_id: int) -> Payment:
        payment = self.repository.get_for_update(payment_id)
        if payment is None:
            raise ValueError(f"Payment {payment_id} not found")
        return payment

    def list(self) -> list[Payment]:
        return self.repository.list()

    def allocations(self, payment_id: int) -> list[PaymentAllocation]:
        self.get(payment_id)
        return self.repository.allocations_for_payment(payment_id)

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

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    def _record_source_evidence(
        self,
        payment: Payment,
        payload: PaymentIngest,
        *,
        actor_id: int | None,
    ) -> PaymentSettlementEvidence:
        canonical_payload = json.dumps(
            payload.raw_payload,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode()
        evidence = PaymentSettlementEvidence(
            organization_id=self.organization_id,
            payment_id=payment.id,
            evidence_type="source_record",
            settlement_reference=payment.payment_reference,
            amount=payment.paid_amount,
            currency=payment.currency,
            received_at=datetime.combine(
                payment.payment_date,
                datetime.min.time(),
                tzinfo=UTC,
            ),
            source_hash=sha256(canonical_payload).hexdigest(),
            actor_id=actor_id,
            reason="Canonical payment source record",
            correlation_id=payment.correlation_id,
            idempotency_key=f"source-payment-{payment.id}",
        )
        self.db.add(evidence)
        self.db.flush()
        return evidence

    def _ensure_source_evidence(
        self,
        payment: Payment,
        *,
        actor_id: int | None,
        correlation_id: str,
    ) -> PaymentSettlementEvidence:
        existing = self.repository.settlement_evidence_for_payment(payment.id)
        if existing:
            return existing[0]
        canonical_payload = json.dumps(
            payment.raw_payload,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode()
        evidence = PaymentSettlementEvidence(
            organization_id=self.organization_id,
            payment_id=payment.id,
            evidence_type="source_record",
            settlement_reference=payment.payment_reference,
            amount=payment.paid_amount,
            currency=payment.currency,
            received_at=datetime.combine(
                payment.payment_date,
                datetime.min.time(),
                tzinfo=UTC,
            ),
            source_hash=sha256(canonical_payload).hexdigest(),
            actor_id=actor_id,
            reason="Canonical payment source record materialized before allocation",
            correlation_id=correlation_id,
            idempotency_key=f"source-payment-{payment.id}",
        )
        self.db.add(evidence)
        self.db.flush()
        return evidence

    @staticmethod
    def _validate_allocation_replay(
        payment: Payment,
        payload: PaymentAllocationBatchCreate,
        rows: list[PaymentAllocation],
    ) -> None:
        for index, (item, row) in enumerate(
            zip(payload.allocations, rows, strict=True)
        ):
            if (
                row.payment_id != payment.id
                or row.claim_id != item.claim_id
                or row.submission_id != item.submission_id
                or row.amount != item.amount.quantize(_MONEY)
                or row.reason != payload.reason.strip()
                or row.item_index != index
                or row.allocation_type != PaymentAllocationType.ALLOCATION
            ):
                raise ValueError("Idempotency key conflicts with allocation batch")
