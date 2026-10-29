from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.audit.actions import AuditAction
from app.audit.service import AuditService
from app.core.dependencies import get_current_organization
from app.db.database import get_db
from app.events.event_types import EventType
from app.events.publisher import EventPublisher
from app.models.user import User
from app.recoveries.schemas import (
    RecoveryAttributionCreate,
    RecoveryAttributionDisputeCreate,
    RecoveryAttributionDisputeRead,
    RecoveryAttributionDisputeResolutionCreate,
    RecoveryAttributionDisputeResolutionResultRead,
    RecoveryAttributionRead,
    RecoveryInterventionCreate,
    RecoveryInterventionRead,
    RecoveryRead,
    RecoveryVerify,
)
from app.recoveries.service import RecoveryAttributionService
from app.security.dependencies import require_permission
from app.security.permissions import Permission

router = APIRouter(prefix="/recoveries", tags=["Recoveries"])


def _correlation_id(request: Request) -> str:
    return str(getattr(request.state, "request_id", None) or "unknown")


def _raise_recovery_error(exc: ValueError) -> None:
    message = str(exc)
    code = (
        status.HTTP_404_NOT_FOUND
        if "not found" in message
        else status.HTTP_409_CONFLICT
        if any(
            term in message
            for term in (
                "already",
                "conflicts with immutable",
                "while attribution is disputed",
            )
        )
        else status.HTTP_400_BAD_REQUEST
    )
    raise HTTPException(status_code=code, detail=message) from exc


@router.get("", response_model=list[RecoveryRead])
def list_recoveries(
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.MANAGE_BILLING)),
):
    return RecoveryAttributionService(db, organization_id).list()


@router.post(
    "/interventions",
    response_model=RecoveryInterventionRead,
    status_code=status.HTTP_201_CREATED,
)
def record_recovery_intervention(
    payload: RecoveryInterventionCreate,
    request: Request,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.MANAGE_BILLING)),
):
    correlation_id = _correlation_id(request)
    try:
        intervention = RecoveryAttributionService(
            db,
            organization_id,
        ).record_intervention(
            payload,
            actor_id=current_user.id,
            correlation_id=correlation_id,
        )
        AuditService(db).log(
            organization_id=organization_id,
            user_id=current_user.id,
            action=AuditAction.RECOVERY_INTERVENTION_RECORDED,
            entity="recovery_intervention",
            entity_id=intervention.id,
            before_state=None,
            after_state={
                "claim_id": intervention.claim_id,
                "submission_id": intervention.submission_id,
                "intervention_type": intervention.intervention_type,
                "occurred_at": intervention.occurred_at.isoformat(),
            },
            reason=intervention.reason,
            correlation_id=correlation_id,
        )
        db.commit()
        db.refresh(intervention)
    except ValueError as exc:
        db.rollback()
        _raise_recovery_error(exc)
    EventPublisher().publish(
        EventType.RECOVERY_INTERVENTION_RECORDED,
        {
            "organization_id": organization_id,
            "intervention_id": intervention.id,
            "claim_id": intervention.claim_id,
            "actor_id": current_user.id,
            "correlation_id": correlation_id,
        },
        organization_id=organization_id,
    )
    return intervention


@router.get("/{recovery_id}", response_model=RecoveryRead)
def get_recovery(
    recovery_id: int,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    _current_user: User = Depends(require_permission(Permission.MANAGE_BILLING)),
):
    try:
        return RecoveryAttributionService(db, organization_id).get(recovery_id)
    except ValueError as exc:
        _raise_recovery_error(exc)


@router.post("/{recovery_id}/verify", response_model=RecoveryRead)
def verify_recovery(
    recovery_id: int,
    payload: RecoveryVerify,
    request: Request,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.MANAGE_BILLING)),
):
    correlation_id = _correlation_id(request)
    try:
        service = RecoveryAttributionService(db, organization_id)
        was_verified = service.get(recovery_id).verified
        recovery = service.verify(
            recovery_id,
            verified_by=current_user.id,
            reason=payload.reason,
        )
        AuditService(db).log(
            organization_id=organization_id,
            user_id=current_user.id,
            action=AuditAction.RECOVERY_VERIFIED,
            entity="recovery",
            entity_id=recovery.id,
            metadata={
                "payment_id": recovery.payment_id,
            },
            before_state={"verified": was_verified},
            after_state={
                "verified": True,
                "verified_by": recovery.verified_by,
                "verified_at": recovery.verified_at.isoformat(),
            },
            reason=recovery.verification_reason,
            correlation_id=correlation_id,
        )
        db.commit()
        db.refresh(recovery)
    except ValueError as exc:
        db.rollback()
        _raise_recovery_error(exc)
    EventPublisher().publish(
        EventType.RECOVERY_VERIFIED,
        {
            "organization_id": organization_id,
            "recovery_id": recovery.id,
            "payment_id": recovery.payment_id,
            "actor_id": current_user.id,
            "correlation_id": correlation_id,
        },
        organization_id=organization_id,
    )
    return recovery


@router.get(
    "/{recovery_id}/interventions",
    response_model=list[RecoveryInterventionRead],
)
def list_recovery_interventions(
    recovery_id: int,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    _current_user: User = Depends(require_permission(Permission.MANAGE_BILLING)),
):
    try:
        return RecoveryAttributionService(
            db,
            organization_id,
        ).interventions(recovery_id)
    except ValueError as exc:
        _raise_recovery_error(exc)


@router.post(
    "/{recovery_id}/attributions",
    response_model=RecoveryAttributionRead,
    status_code=status.HTTP_201_CREATED,
)
def decide_recovery_attribution(
    recovery_id: int,
    payload: RecoveryAttributionCreate,
    request: Request,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.MANAGE_BILLING)),
):
    correlation_id = _correlation_id(request)
    try:
        attribution = RecoveryAttributionService(
            db,
            organization_id,
        ).decide_attribution(
            recovery_id,
            payload,
            actor_id=current_user.id,
            correlation_id=correlation_id,
        )
        AuditService(db).log(
            organization_id=organization_id,
            user_id=current_user.id,
            action=AuditAction.RECOVERY_ATTRIBUTION_DECIDED,
            entity="recovery_attribution_version",
            entity_id=attribution.id,
            before_state=None,
            after_state={
                "recovery_id": recovery_id,
                "version": attribution.version,
                "status": attribution.status,
                "confirmed_amount": str(attribution.confirmed_amount),
                "eligible_amount": str(attribution.eligible_amount),
                "fee_percentage": str(attribution.fee_percentage),
                "vat_percentage": str(attribution.vat_percentage),
            },
            reason=attribution.reason,
            correlation_id=correlation_id,
        )
        db.commit()
        db.refresh(attribution)
    except ValueError as exc:
        db.rollback()
        _raise_recovery_error(exc)
    EventPublisher().publish(
        EventType.RECOVERY_ATTRIBUTION_DECIDED,
        {
            "organization_id": organization_id,
            "recovery_id": recovery_id,
            "attribution_version_id": attribution.id,
            "status": attribution.status,
            "eligible_amount": str(attribution.eligible_amount),
            "actor_id": current_user.id,
            "correlation_id": correlation_id,
        },
        organization_id=organization_id,
    )
    return attribution


@router.get(
    "/{recovery_id}/attributions",
    response_model=list[RecoveryAttributionRead],
)
def list_recovery_attributions(
    recovery_id: int,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    _current_user: User = Depends(require_permission(Permission.MANAGE_BILLING)),
):
    try:
        return RecoveryAttributionService(
            db,
            organization_id,
        ).attributions(recovery_id)
    except ValueError as exc:
        _raise_recovery_error(exc)


@router.post(
    "/{recovery_id}/disputes",
    response_model=RecoveryAttributionDisputeRead,
    status_code=status.HTTP_201_CREATED,
)
def open_recovery_attribution_dispute(
    recovery_id: int,
    payload: RecoveryAttributionDisputeCreate,
    request: Request,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.MANAGE_BILLING)),
):
    correlation_id = _correlation_id(request)
    try:
        dispute = RecoveryAttributionService(
            db,
            organization_id,
        ).open_dispute(
            recovery_id,
            actor_id=current_user.id,
            reason=payload.reason,
            correlation_id=correlation_id,
        )
        AuditService(db).log(
            organization_id=organization_id,
            user_id=current_user.id,
            action=AuditAction.RECOVERY_ATTRIBUTION_DISPUTED,
            entity="recovery_attribution_dispute",
            entity_id=dispute.id,
            before_state={
                "attribution_version_id": dispute.attribution_version.previous_version_id,
            },
            after_state={
                "attribution_version_id": dispute.attribution_version_id,
                "status": "disputed",
            },
            reason=dispute.reason,
            correlation_id=correlation_id,
        )
        db.commit()
        db.refresh(dispute)
    except ValueError as exc:
        db.rollback()
        _raise_recovery_error(exc)
    EventPublisher().publish(
        EventType.RECOVERY_ATTRIBUTION_DISPUTED,
        {
            "organization_id": organization_id,
            "recovery_id": recovery_id,
            "dispute_id": dispute.id,
            "attribution_version_id": dispute.attribution_version_id,
            "actor_id": current_user.id,
            "correlation_id": correlation_id,
        },
        organization_id=organization_id,
    )
    return dispute


@router.get(
    "/{recovery_id}/disputes",
    response_model=list[RecoveryAttributionDisputeRead],
)
def list_recovery_attribution_disputes(
    recovery_id: int,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    _current_user: User = Depends(require_permission(Permission.MANAGE_BILLING)),
):
    try:
        return RecoveryAttributionService(
            db,
            organization_id,
        ).disputes(recovery_id)
    except ValueError as exc:
        _raise_recovery_error(exc)


@router.post(
    "/{recovery_id}/disputes/{dispute_id}/resolve",
    response_model=RecoveryAttributionDisputeResolutionResultRead,
)
def resolve_recovery_attribution_dispute(
    recovery_id: int,
    dispute_id: int,
    payload: RecoveryAttributionDisputeResolutionCreate,
    request: Request,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.MANAGE_BILLING)),
):
    correlation_id = _correlation_id(request)
    try:
        result = RecoveryAttributionService(
            db,
            organization_id,
        ).resolve_dispute(
            recovery_id,
            dispute_id,
            payload,
            actor_id=current_user.id,
            correlation_id=correlation_id,
        )
        AuditService(db).log(
            organization_id=organization_id,
            user_id=current_user.id,
            action=AuditAction.RECOVERY_ATTRIBUTION_DISPUTE_RESOLVED,
            entity="recovery_attribution_dispute_resolution",
            entity_id=result.resolution.id,
            before_state={
                "dispute_id": dispute_id,
                "status": "disputed",
            },
            after_state={
                "outcome": result.resolution.outcome,
                "eligible_amount": str(result.resolution.eligible_amount),
                "attribution_version_id": result.attribution.id,
                "credit_note_id": result.credit_note_id,
            },
            reason=result.resolution.reason,
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
                    "attribution_resolution_id": result.resolution.id,
                },
                reason=result.resolution.reason,
                correlation_id=correlation_id,
            )
        db.commit()
        db.refresh(result.resolution)
        db.refresh(result.attribution)
    except ValueError as exc:
        db.rollback()
        _raise_recovery_error(exc)
    EventPublisher().publish(
        EventType.RECOVERY_ATTRIBUTION_DISPUTE_RESOLVED,
        {
            "organization_id": organization_id,
            "recovery_id": recovery_id,
            "dispute_id": dispute_id,
            "resolution_id": result.resolution.id,
            "attribution_version_id": result.attribution.id,
            "credit_note_id": result.credit_note_id,
            "actor_id": current_user.id,
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
                "attribution_resolution_id": result.resolution.id,
                "correlation_id": correlation_id,
            },
            organization_id=organization_id,
        )
    return result
