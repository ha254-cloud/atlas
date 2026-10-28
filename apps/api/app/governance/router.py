from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_organization
from app.db.database import get_db
from app.documents.retention import (
    DocumentRetentionService,
    RetentionDocumentNotFound,
    RetentionEnforcementDenied,
    RetentionPolicyNotFound,
    RetentionStorageFailure,
)
from app.documents.schemas import (
    DocumentHoldCreate,
    DocumentHoldRead,
    DocumentRetentionRun,
    RetentionEnforceRequest,
    RetentionRunRequest,
)
from app.governance.schemas import (
    ComplianceSummary,
    ConsentCreate,
    ConsentRead,
    RetentionPolicyCreate,
    RetentionPolicyRead,
    SessionRead,
    SessionRevoke,
)
from app.governance.service import (
    ComplianceService,
    ConsentService,
    GovernanceNotFoundError,
    RetentionService,
    SessionService,
)
from app.models.audit_log import AuditLog
from app.models.user import User
from app.schemas.audit_log import AuditLogRead
from app.security.dependencies import require_permission
from app.security.permissions import Permission

router = APIRouter(prefix="/governance", tags=["Governance"])


def _correlation_id(request: Request) -> str:
    return getattr(request.state, "request_id", "governance-api")


@router.get("/summary", response_model=ComplianceSummary)
def compliance_summary(
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.VIEW_GOVERNANCE)),
):
    return ComplianceService(db, organization_id).summary()


@router.get("/audit/correlations/{correlation_id}", response_model=list[AuditLogRead])
def correlation_timeline(
    correlation_id: str,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.VIEW_GOVERNANCE)),
):
    return (
        db.query(AuditLog)
        .filter(
            AuditLog.organization_id == organization_id,
            AuditLog.correlation_id == correlation_id,
        )
        .order_by(AuditLog.created_at, AuditLog.id)
        .all()
    )


@router.post("/patients/{patient_id}/consents", response_model=ConsentRead)
def record_consent(
    patient_id: int,
    payload: ConsentCreate,
    request: Request,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.MANAGE_GOVERNANCE)),
):
    try:
        return ConsentService(db, organization_id).record(
            patient_id, payload, current_user.id, _correlation_id(request)
        )
    except GovernanceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/patients/{patient_id}/consents", response_model=list[ConsentRead])
def list_consents(
    patient_id: int,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.VIEW_GOVERNANCE)),
):
    try:
        return ConsentService(db, organization_id).list(patient_id)
    except GovernanceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/retention-policies", response_model=RetentionPolicyRead)
def create_retention_policy(
    payload: RetentionPolicyCreate,
    request: Request,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.MANAGE_GOVERNANCE)),
):
    return RetentionService(db, organization_id).create(
        payload, current_user.id, _correlation_id(request)
    )


@router.get("/retention-policies", response_model=list[RetentionPolicyRead])
def list_retention_policies(
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.VIEW_GOVERNANCE)),
):
    return RetentionService(db, organization_id).list()


@router.post(
    "/documents/{document_id}/holds",
    response_model=DocumentHoldRead,
)
def record_document_hold(
    document_id: int,
    payload: DocumentHoldCreate,
    request: Request,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.MANAGE_GOVERNANCE)),
):
    try:
        return DocumentRetentionService(db, organization_id).record_hold(
            document_id=document_id,
            hold_type=payload.hold_type,
            active=payload.active,
            reason=payload.reason,
            actor_id=current_user.id,
            correlation_id=_correlation_id(request),
        )
    except RetentionDocumentNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/documents/{document_id}/holds",
    response_model=list[DocumentHoldRead],
)
def list_document_holds(
    document_id: int,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.VIEW_GOVERNANCE)),
):
    try:
        return DocumentRetentionService(db, organization_id).list_holds(document_id)
    except RetentionDocumentNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/retention/documents/dry-run",
    response_model=DocumentRetentionRun,
)
def preview_document_retention(
    payload: RetentionRunRequest,
    request: Request,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.MANAGE_GOVERNANCE)),
):
    try:
        return DocumentRetentionService(db, organization_id).dry_run(
            actor_id=current_user.id,
            correlation_id=_correlation_id(request),
            as_of=payload.as_of,
        )
    except RetentionPolicyNotFound as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post(
    "/retention/documents/enforce",
    response_model=DocumentRetentionRun,
)
def enforce_document_retention(
    payload: RetentionEnforceRequest,
    request: Request,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.MANAGE_GOVERNANCE)),
):
    try:
        return DocumentRetentionService(db, organization_id).enforce(
            actor_id=current_user.id,
            correlation_id=_correlation_id(request),
            expected_policy_version=payload.expected_policy_version,
            confirm=payload.confirm,
            reason=payload.reason,
            as_of=payload.as_of,
        )
    except RetentionPolicyNotFound as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except RetentionEnforcementDenied as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except RetentionStorageFailure as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/sessions", response_model=list[SessionRead])
def list_sessions(
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.MANAGE_GOVERNANCE)),
):
    return SessionService(db, organization_id).list()


@router.post("/sessions/{session_id}/revoke", response_model=SessionRead)
def revoke_session(
    session_id: str,
    payload: SessionRevoke,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.MANAGE_GOVERNANCE)),
):
    try:
        return SessionService(db, organization_id).revoke(
            session_id, current_user.id, payload.reason
        )
    except GovernanceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
