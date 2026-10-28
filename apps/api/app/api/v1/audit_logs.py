"""
Read-only API surface for the audit trail. AuditService writes entries from
throughout the app (claims, appeals, integrations, API keys, auth, imports,
payments); this endpoint is the first way to actually query them — until
now the audit log was write-only.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_organization
from app.db.database import get_db
from app.models.audit_log import AuditLog
from app.models.user import User
from app.schemas.audit_log import AuditLogRead
from app.security.dependencies import require_permission
from app.security.permissions import Permission

router = APIRouter(prefix="/audit-logs", tags=["Audit"])


@router.get("", response_model=list[AuditLogRead])
def list_audit_logs(
    action: str | None = Query(None, description="Filter by exact action, e.g. claim.created"),
    entity: str | None = Query(None, description="Filter by entity type, e.g. claim"),
    user_id: int | None = Query(None, description="Filter by the acting user"),
    correlation_id: str | None = Query(None, description="Filter by correlation ID"),
    since: datetime | None = Query(None, description="Only entries at/after this timestamp"),
    until: datetime | None = Query(None, description="Only entries at/before this timestamp"),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.VIEW_AUDIT_LOG)),
):
    """
    Query the organization's audit trail. Restricted to roles with the
    VIEW_AUDIT_LOG permission (Auditor, Manager, Admin, Owner).
    """
    query = db.query(AuditLog).filter(AuditLog.organization_id == organization_id)

    if action:
        query = query.filter(AuditLog.action == action)
    if entity:
        query = query.filter(AuditLog.entity == entity)
    if user_id is not None:
        query = query.filter(AuditLog.user_id == user_id)
    if correlation_id:
        query = query.filter(AuditLog.correlation_id == correlation_id)
    if since:
        query = query.filter(AuditLog.created_at >= since)
    if until:
        query = query.filter(AuditLog.created_at <= until)

    return query.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit).all()
