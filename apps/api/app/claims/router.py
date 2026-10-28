import csv
import io

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from app.appeals.repository import AppealRepository
from app.appeals.schemas import AppealCreate, AppealRead
from app.audit.actions import AuditAction
from app.audit.service import AuditService
from app.branches.service import ORG_LEVEL_BRANCH_ROLES, BranchService
from app.claims.repository import ClaimRepository
from app.claims.schemas import (
    ClaimAnalysisResponse,
    ClaimCreate,
    ClaimDetailRead,
    ClaimRead,
    ClaimUpdate,
    PatientLookup,
    PayerLookup,
)
from app.claims.service import ClaimService
from app.claims.timeline import ClaimTimeline
from app.claims.validators import ClaimValidationError
from app.core.dependencies import get_current_organization
from app.db.database import get_db
from app.models.appeal import Appeal, AppealStatus
from app.models.claim_analysis import ClaimAnalysis
from app.models.payer import Payer
from app.models.user import User
from app.patients.service import PatientService
from app.repositories.claim_analysis import ClaimAnalysisRepository
from app.security.dependencies import require_permission
from app.security.permissions import Permission
from app.workers.tasks import generate_appeal_task

router = APIRouter(prefix="/claims", tags=["claims"])

CLAIM_EXPORT_FIELDS = (
    "claim_number",
    "patient_first_name",
    "patient_last_name",
    "medical_record_number",
    "payer_code",
    "branch_code",
    "department_code",
    "currency",
    "billed_amount",
    "paid_amount",
    "service_date",
    "status",
    "diagnosis_codes",
    "procedure_codes",
)
CLAIM_EXPORT_TEXT_FIELDS = {
    "claim_number",
    "patient_first_name",
    "patient_last_name",
    "medical_record_number",
    "payer_code",
    "branch_code",
    "department_code",
    "currency",
    "status",
    "diagnosis_codes",
    "procedure_codes",
}


def _spreadsheet_safe_row(row: dict) -> dict:
    return {
        field: (
            f"'{value}"
            if field in CLAIM_EXPORT_TEXT_FIELDS
            and isinstance(value, str)
            and value.startswith(("=", "+", "-", "@", "\t", "\r"))
            else value
        )
        for field, value in row.items()
    }


def _service(db: Session, organization_id: int, current_user: User | None = None) -> ClaimService:
    accessible_branch_ids = None
    if (
        current_user is not None
        and not current_user.is_superuser
        and current_user.role not in ORG_LEVEL_BRANCH_ROLES
    ):
        accessible_branch_ids = [
            branch.id for branch in BranchService(db, organization_id).list_for_user(current_user)
        ]
    return ClaimService(db, organization_id, accessible_branch_ids)


def _require_claim_branch_access(
    db: Session,
    organization_id: int,
    current_user: User,
    branch_id: int | None,
) -> None:
    if current_user.is_superuser or current_user.role in ORG_LEVEL_BRANCH_ROLES:
        return
    if branch_id is None:
        raise HTTPException(status_code=422, detail="branch_id is required for branch-scoped users")
    try:
        BranchService(db, organization_id).require_access(branch_id, current_user)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Branch not found") from exc


@router.get("/lookups/patients", response_model=list[PatientLookup])
def list_patient_lookups(
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.VIEW_CLAIMS)),
):
    patients = PatientService(db, organization_id).list_patients(
        limit=200,
        offset=0,
    )
    return [{"id": p.id, "name": f"{p.first_name} {p.last_name}"} for p in patients]


@router.get("/lookups/payers", response_model=list[PayerLookup])
def list_payer_lookups(
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.VIEW_CLAIMS)),
):
    payers = (
        db.query(Payer).filter(Payer.organization_id == organization_id).order_by(Payer.name).all()
    )
    return [{"id": p.id, "name": p.name} for p in payers]


@router.post("/", response_model=ClaimRead)
def create_claim(
    payload: ClaimCreate,
    request: Request,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.EDIT_CLAIMS)),
):
    _require_claim_branch_access(db, organization_id, current_user, payload.branch_id)
    try:
        claim = _service(db, organization_id, current_user).create_claim(
            payload.model_dump(), actor_id=current_user.id
        )
    except (ClaimValidationError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    AuditService(db).log(
        organization_id=organization_id,
        user_id=current_user.id,
        action=AuditAction.CLAIM_CREATED,
        entity="claim",
        entity_id=claim["id"],
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    return claim


@router.get("/export.csv")
def export_claims(
    request: Request,
    reason: str = Query(min_length=3, max_length=500),
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.EXPORT_CLAIMS)),
):
    rows = _service(db, organization_id, current_user).export_claims()
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=CLAIM_EXPORT_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(_spreadsheet_safe_row(row) for row in rows)

    AuditService(db).log(
        organization_id=organization_id,
        user_id=current_user.id,
        action=AuditAction.CLAIMS_EXPORTED,
        entity="claim",
        ip_address=request.client.host if request.client else None,
        reason=reason,
        metadata={"format": "csv", "row_count": len(rows)},
    )
    db.commit()
    return Response(
        content="\ufeff" + output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="atlas-claims.csv"'},
    )


@router.get("/{claim_id}", response_model=ClaimDetailRead)
def get_claim(
    claim_id: int,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.VIEW_CLAIMS)),
):
    claim = _service(db, organization_id, current_user).get_claim(claim_id)
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    return claim


@router.get("/{claim_id}/analysis", response_model=ClaimAnalysisResponse)
def get_claim_analysis(
    claim_id: int,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.VIEW_CLAIMS)),
):
    claim = _service(db, organization_id, current_user).get_claim(claim_id)
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    analysis = ClaimAnalysisRepository(db, organization_id).get_latest(claim_id)
    if analysis is None:
        return {"status": "pending"}

    return {
        "status": analysis.analysis_status.value,
        "risk_score": float(analysis.risk_score) if analysis.risk_score is not None else None,
        "priority": analysis.priority.upper() if analysis.priority else None,
        "confidence": (
            float(analysis.confidence_score) / 100
            if analysis.confidence_score is not None
            else None
        ),
        "recovery_probability": (
            float(analysis.recovery_probability) / 100
            if analysis.recovery_probability is not None
            else None
        ),
        "recommended_action": analysis.recommended_action,
        "summary": analysis.ai_summary,
        "required_documents": analysis.required_documents or [],
    }


@router.get("/{claim_id}/appeals", response_model=list[AppealRead])
def list_claim_appeals(
    claim_id: int,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.VIEW_CLAIMS)),
):
    if not _service(db, organization_id, current_user).get_claim(claim_id):
        raise HTTPException(status_code=404, detail="Claim not found")
    return AppealRepository(db, organization_id).history(claim_id)


@router.post(
    "/{claim_id}/appeals/generate",
    response_model=AppealRead,
    status_code=202,
)
def queue_claim_appeal_generation(
    claim_id: int,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.GENERATE_APPEALS)),
):
    claim = ClaimRepository(db, organization_id).get(claim_id)
    if claim is None:
        raise HTTPException(status_code=404, detail="Claim not found")
    if claim.analysis is None:
        raise HTTPException(status_code=409, detail="Claim analysis is required")

    repository = AppealRepository(db, organization_id)
    appeal = repository.latest(claim_id)
    if appeal is None or appeal.status != AppealStatus.DRAFT:
        appeal = repository.create(
            Appeal(
                organization_id=organization_id,
                claim_id=claim_id,
                analysis_id=claim.analysis.id,
                status=AppealStatus.DRAFT,
                title="Generating appeal",
                appeal_text="",
                generated_by=str(current_user.id),
            )
        )
        db.commit()
        db.refresh(appeal)

    try:
        generate_appeal_task.delay(
            claim_id,
            organization_id,
            appeal.id,
            current_user.id,
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Appeal queue unavailable") from exc
    return appeal


@router.post("/{claim_id}/appeals", response_model=AppealRead, status_code=201)
def create_claim_appeal(
    claim_id: int,
    payload: AppealCreate,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.GENERATE_APPEALS)),
):
    if payload.claim_id != claim_id:
        raise HTTPException(status_code=400, detail="Claim ID does not match route")
    if not _service(db, organization_id, current_user).get_claim(claim_id):
        raise HTTPException(status_code=404, detail="Claim not found")
    if not payload.body:
        raise HTTPException(status_code=422, detail="Appeal body is required")
    if payload.analysis_id is not None:
        analysis = (
            db.query(ClaimAnalysis)
            .filter(
                ClaimAnalysis.id == payload.analysis_id,
                ClaimAnalysis.claim_id == claim_id,
                ClaimAnalysis.organization_id == organization_id,
            )
            .first()
        )
        if analysis is None:
            raise HTTPException(status_code=404, detail="Claim analysis not found")

    appeal = Appeal(
        organization_id=organization_id,
        claim_id=claim_id,
        analysis_id=payload.analysis_id,
        recovery_case_id=payload.recovery_case_id,
        status=AppealStatus.DRAFT,
        title=payload.title,
        appeal_text=payload.body,
        confidence=payload.confidence,
        required_documents=payload.required_documents,
        missing_documents=payload.missing_documents,
        references=payload.references,
        generated_by=str(current_user.id),
    )
    AppealRepository(db, organization_id).create(appeal)
    db.commit()
    db.refresh(appeal)
    return appeal


@router.get("/", response_model=list[ClaimRead])
def list_claims(
    limit: int = 100,
    offset: int = 0,
    search: str | None = None,
    status: str | None = None,
    payer_id: int | None = None,
    priority: str | None = None,
    assigned_user_id: int | None = None,
    min_risk_score: float | None = None,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.VIEW_CLAIMS)),
):
    return _service(db, organization_id, current_user).list_claims(
        limit,
        offset,
        search=search,
        status=status,
        payer_id=payer_id,
        priority=priority,
        assigned_user_id=assigned_user_id,
        min_risk_score=min_risk_score,
    )


@router.patch("/{claim_id}", response_model=ClaimRead)
def update_claim(
    claim_id: int,
    payload: ClaimUpdate,
    request: Request,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.EDIT_CLAIMS)),
):
    service = _service(db, organization_id, current_user)
    previous = service.get_claim(claim_id)
    if not previous:
        raise HTTPException(status_code=404, detail="Claim not found")

    fields = payload.model_dump(exclude_unset=True, exclude={"reason"})
    _require_claim_branch_access(
        db,
        organization_id,
        current_user,
        fields.get("branch_id", previous.get("branch_id")),
    )
    claim = service.update_claim(claim_id, fields, actor_id=current_user.id)
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    changed_fields = sorted(fields)
    AuditService(db).log(
        organization_id=organization_id,
        user_id=current_user.id,
        action=AuditAction.CLAIM_UPDATED,
        entity="claim",
        entity_id=claim["id"],
        ip_address=request.client.host if request.client else None,
        reason=payload.reason or f"Claim fields updated: {', '.join(changed_fields)}",
        before_state=jsonable_encoder({field: previous[field] for field in changed_fields}),
        after_state=jsonable_encoder({field: claim[field] for field in changed_fields}),
        metadata={"changed_fields": changed_fields},
    )
    db.commit()
    return claim


@router.delete("/{claim_id}")
def delete_claim(
    claim_id: int,
    request: Request,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.EDIT_CLAIMS)),
):
    ok = _service(db, organization_id, current_user).delete_claim(claim_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Claim not found")

    AuditService(db).log(
        organization_id=organization_id,
        user_id=current_user.id,
        action=AuditAction.CLAIM_DELETED,
        entity="claim",
        entity_id=claim_id,
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    return {"deleted": True}


@router.get("/{claim_id}/timeline")
def get_claim_timeline(
    claim_id: int,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.VIEW_CLAIMS)),
):
    """
    Return the immutable event history for a claim.
    Events are sorted chronologically — oldest first.
    """
    timeline = ClaimTimeline(db)
    events = timeline.get_timeline(claim_id, organization_id)
    return [
        {
            "id": e.id,
            "event_type": e.event_type.value,
            "description": e.description,
            "actor_id": e.actor_id,
            "metadata": e.event_metadata,
            "occurred_at": e.occurred_at.isoformat() if e.occurred_at else None,
        }
        for e in events
    ]
