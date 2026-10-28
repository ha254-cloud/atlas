from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session

from app.appeals.evidence import MissingEvidenceError
from app.appeals.schemas import (
    AppealCreate,
    AppealListItem,
    AppealRead,
    AppealSubmitRequest,
    AppealUpdate,
)
from app.appeals.service import AppealService
from app.audit.actions import AuditAction
from app.audit.service import AuditService
from app.core.dependencies import get_current_organization
from app.db.database import get_db
from app.documents.storage import read_file
from app.models.appeal import AppealStatus
from app.models.user import User
from app.organizations.entitlements import Feature, require_feature
from app.security.dependencies import require_permission
from app.security.permissions import Permission
from app.services.pdf.appeal_pdf import AppealPDFService

router = APIRouter(
    prefix="/appeals",
    tags=["Appeals"],
    dependencies=[Depends(require_feature(Feature.AI_APPEAL))],
)


def _svc(db: Session, org: int) -> AppealService:
    return AppealService(db, org)


@router.get("", response_model=list[AppealListItem])
def list_appeals(
    status: AppealStatus | None = Query(None),
    search: str | None = Query(None, max_length=100),
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.VIEW_CLAIMS)),
):
    appeals = AppealService(db, organization_id).repo.list(
        status=status,
        search=search,
        limit=limit,
        offset=offset,
    )
    return [
        AppealListItem(
            **AppealRead.model_validate(appeal).model_dump(),
            claim_number=appeal.claim.claim_number,
            payer_name=appeal.claim.payer.name,
            patient_name=f"{appeal.claim.patient.first_name} {appeal.claim.patient.last_name}",
            billed_amount=float(appeal.claim.billed_amount),
            service_date=appeal.claim.service_date,
        )
        for appeal in appeals
    ]


@router.post("", response_model=AppealRead)
async def generate_appeal(
    payload: AppealCreate,
    request: Request,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.GENERATE_APPEALS)),
):
    """Generate an AI appeal draft. Always created as DRAFT — human reviews before submitting.
    If `require_evidence` is set and required supporting documents can't be
    verified on file, generation is refused with a 422 instead of drafting
    an appeal Atlas already knows is missing evidence."""
    try:
        appeal = await _svc(db, organization_id).generate_appeal(
            payload.claim_id,
            payload.recovery_case_id,
            require_evidence=payload.require_evidence,
        )
    except MissingEvidenceError as exc:
        raise HTTPException(
            status_code=422,
            detail={"message": str(exc), "missing_documents": exc.missing_documents},
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    AuditService(db).log(
        organization_id=organization_id,
        user_id=current_user.id,
        action=AuditAction.APPEAL_GENERATED,
        entity="appeal",
        entity_id=appeal.id,
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    return appeal


@router.post("/sectioned", response_model=AppealRead)
async def generate_sectioned_appeal(
    payload: AppealCreate,
    request: Request,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.GENERATE_APPEALS)),
):
    """
    Generate a sectioned appeal draft.
    Each section (Introduction, Medical Necessity, etc.) is generated independently
    so specialists can edit specific sections without rewriting the whole letter.
    """
    try:
        appeal = await _svc(db, organization_id).generate_sectioned_appeal(
            payload.claim_id,
            payload.recovery_case_id,
            require_evidence=payload.require_evidence,
        )
    except MissingEvidenceError as exc:
        raise HTTPException(
            status_code=422,
            detail={"message": str(exc), "missing_documents": exc.missing_documents},
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    AuditService(db).log(
        organization_id=organization_id,
        user_id=current_user.id,
        action=AuditAction.APPEAL_GENERATED,
        entity="appeal",
        entity_id=appeal.id,
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    return appeal


@router.get("/claim/{claim_id}", response_model=list[AppealRead])
def list_appeals_for_claim(
    claim_id: int,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.VIEW_CLAIMS)),
):
    return _svc(db, organization_id).list_for_claim(claim_id)


@router.get("/{appeal_id}", response_model=AppealRead)
def get_appeal(
    appeal_id: int,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.VIEW_CLAIMS)),
):
    appeal = _svc(db, organization_id).get_appeal(appeal_id)
    if not appeal:
        raise HTTPException(status_code=404, detail="Appeal not found")
    return appeal


@router.patch("/{appeal_id}", response_model=AppealRead)
def update_appeal(
    appeal_id: int,
    payload: AppealUpdate,
    request: Request,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.GENERATE_APPEALS)),
):
    """Edit the draft appeal text or a specific section before submission."""
    svc = _svc(db, organization_id)
    if payload.appeal_text is not None:
        existing = svc.get_appeal(appeal_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Appeal not found")
        before_version = existing.current_version
        try:
            appeal = svc.update_appeal_text(
                appeal_id,
                payload.appeal_text,
                edited_by=current_user.id,
                sections=payload.sections,
            )
        except ValueError as exc:
            db.rollback()
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        if not appeal:
            raise HTTPException(status_code=404, detail="Appeal not found")
        AuditService(db).log(
            organization_id=organization_id,
            user_id=current_user.id,
            action=AuditAction.APPEAL_EDITED,
            entity="appeal",
            entity_id=appeal.id,
            ip_address=request.client.host if request.client else None,
            correlation_id=getattr(request.state, "request_id", None),
            reason="Appeal letter edited before approval",
            before_state={"version": before_version, "status": appeal.status.value},
            after_state={"version": appeal.current_version, "status": appeal.status.value},
        )
        db.commit()
        db.refresh(appeal)
        return appeal
    raise HTTPException(status_code=400, detail="Nothing to update")


@router.put("/{appeal_id}", response_model=AppealRead)
def replace_appeal_draft(
    appeal_id: int,
    payload: AppealUpdate,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.GENERATE_APPEALS)),
):
    svc = _svc(db, organization_id)
    appeal = svc.get_appeal(appeal_id)
    if appeal is None:
        raise HTTPException(status_code=404, detail="Appeal not found")
    if appeal.status != AppealStatus.DRAFT:
        raise HTTPException(status_code=409, detail="Only draft appeals can be updated")
    if payload.status is not None:
        raise HTTPException(
            status_code=409, detail="Use an appeal lifecycle endpoint to change status"
        )

    fields = payload.model_dump(
        exclude_unset=True,
        exclude={"appeal_text", "body", "sections", "status"},
    )
    body = payload.body if payload.body is not None else payload.appeal_text
    if body is not None:
        appeal = svc.update_appeal_text(
            appeal_id,
            body,
            edited_by=current_user.id,
            sections=payload.sections,
        )
    if fields:
        appeal = svc.repo.update(appeal_id, **fields)
    if appeal is None:
        raise HTTPException(status_code=400, detail="Nothing to update")
    db.commit()
    db.refresh(appeal)
    return appeal


@router.delete("/{appeal_id}", status_code=204)
def delete_appeal_draft(
    appeal_id: int,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.GENERATE_APPEALS)),
):
    repo = _svc(db, organization_id).repo
    appeal = repo.get(appeal_id)
    if appeal is None:
        raise HTTPException(status_code=404, detail="Appeal not found")
    if not repo.delete_draft(appeal_id):
        raise HTTPException(status_code=409, detail="Only draft appeals can be deleted")
    db.commit()


@router.post("/{appeal_id}/review", response_model=AppealRead)
def submit_for_review(
    appeal_id: int,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.GENERATE_APPEALS)),
):
    """Send a draft appeal to a revenue specialist for human review."""
    try:
        return _svc(db, organization_id).submit_for_review(appeal_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/{appeal_id}/approve", response_model=AppealRead)
def approve_appeal(
    appeal_id: int,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.GENERATE_APPEALS)),
):
    """A human reviewer approves the appeal — required before submission."""
    try:
        appeal = _svc(db, organization_id).approve_appeal(
            appeal_id,
            actor_id=current_user.id,
        )
        AppealPDFService(db, organization_id).create_document(appeal, current_user.id)
        db.commit()
        db.refresh(appeal)
        return appeal
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/{appeal_id}/pdf")
def download_appeal_pdf(
    appeal_id: int,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.VIEW_CLAIMS)),
):
    appeal = _svc(db, organization_id).get_appeal(appeal_id)
    if appeal is None:
        raise HTTPException(status_code=404, detail="Appeal not found")
    if appeal.pdf_document is None:
        raise HTTPException(status_code=409, detail="Approved appeal PDF is not available")
    return Response(
        content=read_file(appeal.pdf_document.storage_path),
        media_type="application/pdf",
        headers={"Content-Disposition": (f'attachment; filename="{appeal.pdf_document.filename}"')},
    )


@router.post("/{appeal_id}/reject", response_model=AppealRead)
def reject_appeal(
    appeal_id: int,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.GENERATE_APPEALS)),
):
    """A human reviewer rejects the appeal — it will not be submitted as-is."""
    try:
        return _svc(db, organization_id).reject_appeal(appeal_id, actor_id=current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/{appeal_id}/submit", response_model=AppealRead)
def submit_appeal(
    appeal_id: int,
    request: Request,
    payload: AppealSubmitRequest,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.SUBMIT_APPEALS)),
):
    """Record an externally completed manual submission and its payer reference.

    Electronic delivery uses the submission engine. Both paths require every
    readiness check to pass; AI drafts are never auto-submitted.
    """
    try:
        appeal = _svc(db, organization_id).submit_appeal(
            appeal_id,
            submitted_by=current_user.id,
            confirmation_number=payload.confirmation_number,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    AuditService(db).log(
        organization_id=organization_id,
        user_id=current_user.id,
        action=AuditAction.APPEAL_SUBMITTED,
        entity="appeal",
        entity_id=appeal.id,
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    return appeal


@router.get("/{appeal_id}/readiness")
def check_submission_readiness(
    appeal_id: int,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.VIEW_CLAIMS)),
):
    """Preview whether an appeal is ready for submission without attempting
    it — returns the list of blocking reasons, if any (empty means ready)."""
    try:
        blockers = _svc(db, organization_id).check_submission_readiness(appeal_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"ready": not blockers, "blockers": blockers}


@router.post("/{appeal_id}/regenerate", response_model=AppealRead)
async def regenerate_appeal(
    appeal_id: int,
    require_evidence: bool = False,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.GENERATE_APPEALS)),
):
    """AI Revision \u2014 re-run generation for a draft/in-review appeal. Snapshots
    the prior content as a new AppealVersion (v1 -> v2 -> ...) before
    overwriting it, same as a manual edit."""
    try:
        return await _svc(db, organization_id).regenerate_appeal(
            appeal_id, require_evidence=require_evidence
        )
    except MissingEvidenceError as exc:
        raise HTTPException(
            status_code=422,
            detail={"message": str(exc), "missing_documents": exc.missing_documents},
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
