from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from app.audit.actions import AuditAction
from app.audit.service import AuditService
from app.billing.service import RecoveryFeeScheduleService
from app.core.dependencies import get_current_organization
from app.db.database import get_db
from app.events.event_types import EventType
from app.events.publisher import EventPublisher
from app.models.claim import Claim
from app.models.recovery import Recovery
from app.models.user import User
from app.payments.models import Payment
from app.payments.schemas import (
    ClaimPaymentTrackingRead,
    PaymentAllocationAdjustmentCreate,
    PaymentAllocationBatchCreate,
    PaymentAllocationBatchRead,
    PaymentAllocationRead,
    PaymentIngest,
    PaymentMatch,
    PaymentMatchCandidate,
    RecoveryFeeScheduleCreate,
    RecoveryFeeScheduleRead,
    SettlementEvidenceCreate,
    SettlementEvidenceRead,
)
from app.payments.schemas import (
    PaymentRead as PaymentRecordRead,
)
from app.payments.service import PaymentService
from app.payments.tracking import ClaimPaymentTrackingService
from app.security.dependencies import require_permission
from app.security.permissions import Permission

router = APIRouter(prefix="/payments", tags=["Payments"])


class PaymentSummary(BaseModel):
    total_recovered: float
    total_fees: float
    net_recovered: float
    payment_count: int
    invoices_generated: int


class PaymentRead(BaseModel):
    payment_id: int
    recovery_id: int | None
    claim_id: int
    claim_number: str
    payer: str
    recovered_amount: float
    atlas_fee: float
    net_amount: float
    received_at: datetime
    currency: str
    payment_status: str
    payment_source: str
    recovery_verified: bool
    attribution_status: str | None
    attributed_eligible_amount: float | None
    invoice_id: int | None
    invoice_generated: bool


class PaymentsResponse(BaseModel):
    summary: PaymentSummary
    payments: list[PaymentRead]


@router.get(
    "/claims/{claim_id}/tracking",
    response_model=ClaimPaymentTrackingRead,
)
def get_claim_payment_tracking(
    claim_id: int,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.VIEW_ANALYTICS)),
) -> ClaimPaymentTrackingRead:
    try:
        return ClaimPaymentTrackingService(db, organization_id).get(claim_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("", response_model=PaymentsResponse)
def list_payments(
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.VIEW_ANALYTICS)),
) -> PaymentsResponse:
    rows = (
        db.query(Payment)
        .options(
            joinedload(Payment.recoveries).joinedload(Recovery.claim).joinedload(Claim.payer),
            joinedload(Payment.recoveries).joinedload(Recovery.invoice_line),
        )
        .filter(Payment.organization_id == organization_id)
        .order_by(Payment.payment_date.desc(), Payment.id.desc())
        .all()
    )

    payments = []
    for row in rows:
        for recovery in row.recoveries:
            recovered = float(recovery.recovered_amount)
            fee = float(recovery.atlas_fee_amount)
            invoice_line = recovery.invoice_line
            attribution = recovery.current_attribution
            payments.append(
                PaymentRead(
                    payment_id=row.id,
                    recovery_id=recovery.id,
                    claim_id=recovery.claim_id,
                    claim_number=recovery.claim.claim_number,
                    payer=recovery.claim.payer.name,
                    recovered_amount=recovered,
                    atlas_fee=fee,
                    net_amount=recovered - fee,
                    received_at=datetime.combine(
                        row.payment_date,
                        datetime.min.time(),
                    ),
                    currency=row.currency,
                    payment_status=row.status.value,
                    payment_source=row.source.value,
                    recovery_verified=recovery.verified,
                    attribution_status=attribution.status if attribution else None,
                    attributed_eligible_amount=(
                        float(attribution.eligible_amount)
                        if attribution is not None
                        else None
                    ),
                    invoice_id=invoice_line.invoice_id if invoice_line else None,
                    invoice_generated=invoice_line is not None,
                )
            )

    verified = [row for row in payments if row.recovery_verified]
    total_recovered = sum(row.recovered_amount for row in verified)
    total_fees = sum(row.atlas_fee for row in verified)
    return PaymentsResponse(
        summary=PaymentSummary(
            total_recovered=total_recovered,
            total_fees=total_fees,
            net_recovered=total_recovered - total_fees,
            payment_count=len(rows),
            invoices_generated=sum(1 for row in payments if row.invoice_generated),
        ),
        payments=payments,
    )


@router.post("", response_model=PaymentRecordRead, status_code=status.HTTP_201_CREATED)
def ingest_payment(
    payload: PaymentIngest,
    response: Response,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.MANAGE_BILLING)),
    correlation_id: str | None = Header(default=None, alias="X-Correlation-ID"),
):
    try:
        result = PaymentService(db, organization_id).ingest(
            payload,
            correlation_id=correlation_id,
            actor_id=current_user.id,
        )
        if result.created:
            AuditService(db).log(
                organization_id=organization_id,
                user_id=current_user.id,
                action=AuditAction.PAYMENT_RECEIVED,
                entity="payment",
                entity_id=result.payment.id,
                metadata={
                    "source": result.payment.source.value,
                },
                before_state=None,
                after_state={
                    "payment_reference": result.payment.payment_reference,
                    "paid_amount": str(result.payment.paid_amount),
                    "claim_id": result.payment.claim_id,
                },
                reason="Payment ingestion",
                correlation_id=result.payment.correlation_id,
            )
        else:
            response.status_code = status.HTTP_200_OK
        db.commit()
        db.refresh(result.payment)
    except ValueError as exc:
        db.rollback()
        message = str(exc)
        code = (
            status.HTTP_409_CONFLICT
            if "conflicts with immutable" in message
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=code, detail=message) from exc

    if result.created:
        EventPublisher().publish(
            EventType.PAYMENT_POSTED,
            {
                "organization_id": organization_id,
                "payment_id": result.payment.id,
                "claim_id": result.payment.claim_id,
                "correlation_id": result.payment.correlation_id,
                "paid_amount": float(result.payment.paid_amount),
            },
        )
    return result.payment


@router.get("/records", response_model=list[PaymentRecordRead])
def list_payment_records(
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.MANAGE_BILLING)),
):
    return PaymentService(db, organization_id).list()


@router.get("/records/{payment_id}", response_model=PaymentRecordRead)
def get_payment_record(
    payment_id: int,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.MANAGE_BILLING)),
):
    try:
        return PaymentService(db, organization_id).get(payment_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/records/{payment_id}/settlement-evidence",
    response_model=list[SettlementEvidenceRead],
)
def list_payment_settlement_evidence(
    payment_id: int,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.MANAGE_BILLING)),
):
    try:
        return PaymentService(db, organization_id).settlement_evidence(payment_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/records/{payment_id}/settlement-evidence",
    response_model=SettlementEvidenceRead,
    status_code=status.HTTP_201_CREATED,
)
def record_payment_settlement_evidence(
    payment_id: int,
    payload: SettlementEvidenceCreate,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.MANAGE_BILLING)),
):
    correlation_id = getattr(request.state, "request_id", None)
    try:
        evidence, created = PaymentService(
            db,
            organization_id,
        ).record_settlement_evidence(
            payment_id,
            payload,
            actor_id=current_user.id,
            correlation_id=correlation_id,
        )
        if created:
            AuditService(db).log(
                organization_id=organization_id,
                user_id=current_user.id,
                action=AuditAction.PAYMENT_SETTLEMENT_EVIDENCE_RECORDED,
                entity="payment_settlement_evidence",
                entity_id=evidence.id,
                before_state=None,
                after_state={
                    "payment_id": payment_id,
                    "evidence_type": evidence.evidence_type,
                    "settlement_reference": evidence.settlement_reference,
                    "amount": str(evidence.amount),
                    "currency": evidence.currency,
                    "source_hash": evidence.source_hash,
                },
                reason=evidence.reason,
                correlation_id=correlation_id,
            )
        else:
            response.status_code = status.HTTP_200_OK
        db.commit()
        db.refresh(evidence)
    except ValueError as exc:
        db.rollback()
        code = (
            status.HTTP_409_CONFLICT
            if "Idempotency key conflicts" in str(exc)
            else status.HTTP_404_NOT_FOUND
            if "not found" in str(exc)
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=code, detail=str(exc)) from exc
    if created:
        EventPublisher().publish(
            EventType.PAYMENT_SETTLEMENT_EVIDENCE_RECORDED,
            {
                "organization_id": organization_id,
                "payment_id": payment_id,
                "settlement_evidence_id": evidence.id,
                "correlation_id": correlation_id,
            },
            organization_id=organization_id,
        )
    return evidence


@router.get(
    "/records/{payment_id}/allocations",
    response_model=list[PaymentAllocationRead],
)
def list_payment_allocations(
    payment_id: int,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.MANAGE_BILLING)),
):
    try:
        return PaymentService(db, organization_id).allocations(payment_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/records/{payment_id}/allocations",
    response_model=PaymentAllocationBatchRead,
    status_code=status.HTTP_201_CREATED,
)
def allocate_payment(
    payment_id: int,
    payload: PaymentAllocationBatchCreate,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.MANAGE_BILLING)),
):
    correlation_id = getattr(request.state, "request_id", None)
    try:
        result = PaymentService(db, organization_id).allocate(
            payment_id,
            payload,
            actor_id=current_user.id,
            actor_type="user",
            correlation_id=correlation_id,
        )
        if result.created:
            AuditService(db).log(
                organization_id=organization_id,
                user_id=current_user.id,
                action=AuditAction.PAYMENT_ALLOCATED,
                entity="payment",
                entity_id=payment_id,
                before_state={
                    "allocated_amount": str(
                        result.allocated_amount
                        - sum(row.amount for row in result.allocations)
                    )
                },
                after_state={
                    "allocation_ids": [row.id for row in result.allocations],
                    "allocated_amount": str(result.allocated_amount),
                    "unallocated_amount": str(result.unallocated_amount),
                },
                reason=payload.reason,
                correlation_id=correlation_id,
            )
        else:
            response.status_code = status.HTTP_200_OK
        db.commit()
        for allocation in result.allocations:
            db.refresh(allocation)
    except ValueError as exc:
        db.rollback()
        code = (
            status.HTTP_409_CONFLICT
            if "Idempotency key conflicts" in str(exc)
            or "incomplete" in str(exc)
            else status.HTTP_404_NOT_FOUND
            if "not found" in str(exc)
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=code, detail=str(exc)) from exc
    if result.created:
        EventPublisher().publish(
            EventType.PAYMENT_ALLOCATED,
            {
                "organization_id": organization_id,
                "payment_id": payment_id,
                "allocation_ids": [row.id for row in result.allocations],
                "allocated_amount": float(result.allocated_amount),
                "unallocated_amount": float(result.unallocated_amount),
                "correlation_id": correlation_id,
            },
            organization_id=organization_id,
        )
    return PaymentAllocationBatchRead(
        allocations=result.allocations,
        created=result.created,
        allocated_amount=result.allocated_amount,
        unallocated_amount=result.unallocated_amount,
    )


@router.post(
    "/allocations/{allocation_id}/adjustments",
    response_model=PaymentAllocationRead,
    status_code=status.HTTP_201_CREATED,
)
def adjust_payment_allocation(
    allocation_id: int,
    payload: PaymentAllocationAdjustmentCreate,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.MANAGE_BILLING)),
):
    correlation_id = getattr(request.state, "request_id", None)
    try:
        result = PaymentService(db, organization_id).adjust_allocation(
            allocation_id,
            payload,
            actor_id=current_user.id,
            correlation_id=correlation_id,
        )
        if result.created:
            AuditService(db).log(
                organization_id=organization_id,
                user_id=current_user.id,
                action=AuditAction.PAYMENT_ALLOCATION_ADJUSTED,
                entity="payment_allocation",
                entity_id=result.allocation.id,
                before_state={"parent_allocation_id": allocation_id},
                after_state={
                    "adjustment_type": result.allocation.allocation_type,
                    "amount": str(result.allocation.amount),
                    "credit_note_id": result.credit_note_id,
                },
                reason=result.allocation.reason,
                correlation_id=correlation_id,
            )
            if result.credit_note_id is not None:
                AuditService(db).log(
                    organization_id=organization_id,
                    user_id=current_user.id,
                    action=AuditAction.INVOICE_CREDIT_NOTE_ISSUED,
                    entity="invoice_credit_note",
                    entity_id=result.credit_note_id,
                    before_state=None,
                    after_state={
                        "payment_allocation_id": result.allocation.id,
                    },
                    reason=result.allocation.reason,
                    correlation_id=correlation_id,
                )
        else:
            response.status_code = status.HTTP_200_OK
        db.commit()
        db.refresh(result.allocation)
    except ValueError as exc:
        db.rollback()
        code = (
            status.HTTP_409_CONFLICT
            if "Idempotency key conflicts" in str(exc)
            else status.HTTP_404_NOT_FOUND
            if "not found" in str(exc)
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=code, detail=str(exc)) from exc
    if result.created:
        EventPublisher().publish(
            EventType.PAYMENT_ALLOCATION_ADJUSTED,
            {
                "organization_id": organization_id,
                "payment_id": result.allocation.payment_id,
                "allocation_id": result.allocation.id,
                "parent_allocation_id": allocation_id,
                "adjustment_type": result.allocation.allocation_type,
                "credit_note_id": result.credit_note_id,
                "correlation_id": correlation_id,
            },
            organization_id=organization_id,
        )
        if result.credit_note_id is not None:
            EventPublisher().publish(
                EventType.INVOICE_CREDIT_NOTE_ISSUED,
                {
                    "organization_id": organization_id,
                    "credit_note_id": result.credit_note_id,
                    "payment_allocation_id": result.allocation.id,
                    "correlation_id": correlation_id,
                },
                organization_id=organization_id,
            )
    return result.allocation


@router.get(
    "/records/{payment_id}/candidates",
    response_model=list[PaymentMatchCandidate],
)
def list_payment_match_candidates(
    payment_id: int,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.MANAGE_BILLING)),
):
    try:
        return PaymentService(db, organization_id).candidates(payment_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{payment_id}/match", response_model=PaymentRecordRead)
def match_payment_record(
    payment_id: int,
    payload: PaymentMatch,
    request: Request,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.MANAGE_BILLING)),
):
    try:
        request_correlation_id = getattr(request.state, "request_id", None)
        payment = PaymentService(db, organization_id).match(
            payment_id,
            claim_id=payload.claim_id,
            submission_id=payload.submission_id,
            matched_by=current_user.id,
            reason=payload.reason,
            correlation_id=request_correlation_id,
        )
        AuditService(db).log(
            organization_id=organization_id,
            user_id=current_user.id,
            action=AuditAction.PAYMENT_MATCHED,
            entity="payment",
            entity_id=payment.id,
            before_state={"claim_id": None, "submission_id": None},
            after_state={
                "claim_id": payment.claim_id,
                "submission_id": payment.submission_id,
                "matching_method": payment.matching_method,
            },
            reason=payment.matching_reason,
            correlation_id=request_correlation_id,
        )
        db.commit()
        db.refresh(payment)
        EventPublisher().publish(
            EventType.PAYMENT_MATCHED,
            {
                "organization_id": organization_id,
                "payment_id": payment.id,
                "claim_id": payment.claim_id,
                "recovery_id": payment.recovery.id if payment.recovery else None,
                "actor_id": current_user.id,
                "correlation_id": request_correlation_id,
            },
            organization_id=organization_id,
        )
        return payment
    except ValueError as exc:
        db.rollback()
        message = str(exc)
        code = (
            status.HTTP_409_CONFLICT
            if "already matched" in message
            else status.HTTP_404_NOT_FOUND
            if "not found" in message
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=code, detail=message) from exc


@router.get("/fee-schedules", response_model=list[RecoveryFeeScheduleRead])
def list_fee_schedules(
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.MANAGE_BILLING)),
):
    return RecoveryFeeScheduleService(db, organization_id).repository.list()


@router.post(
    "/fee-schedules",
    response_model=RecoveryFeeScheduleRead,
    status_code=status.HTTP_201_CREATED,
)
def create_fee_schedule(
    payload: RecoveryFeeScheduleCreate,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.MANAGE_BILLING)),
):
    try:
        schedule = RecoveryFeeScheduleService(db, organization_id).create(
            **payload.model_dump(),
            created_by=current_user.id,
        )
        AuditService(db).log(
            organization_id=organization_id,
            user_id=current_user.id,
            action=AuditAction.RECOVERY_FEE_CONFIGURED,
            entity="recovery_fee_schedule",
            entity_id=schedule.id,
            metadata={
                "before": None,
                "after": {
                    "fee_percentage": str(schedule.fee_percentage),
                    "vat_percentage": str(schedule.vat_percentage),
                    "currency": schedule.currency,
                    "payment_terms_days": schedule.payment_terms_days,
                    "dispute_period_days": schedule.dispute_period_days,
                    "effective_from": schedule.effective_from.isoformat(),
                    "effective_to": (
                        schedule.effective_to.isoformat() if schedule.effective_to else None
                    ),
                },
                "reason": schedule.reason,
            },
        )
        db.commit()
        db.refresh(schedule)
        return schedule
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
