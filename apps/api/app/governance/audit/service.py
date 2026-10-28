from sqlalchemy.orm import Session

from app.audit.actions import AuditAction
from app.governance.audit.context import current_audit_context
from app.models.audit_log import AuditLog

SENSITIVE_KEYS = ("password", "token", "secret", "authorization", "cookie")


def redact_sensitive(value):
    if isinstance(value, dict):
        return {
            key: "[REDACTED]"
            if any(term in key.lower() for term in SENSITIVE_KEYS)
            else redact_sensitive(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_sensitive(item) for item in value]
    return value


class AuditService:
    """Append-only audit writer with request evidence inherited automatically."""

    def __init__(self, db: Session):
        self.db = db

    def log(
        self,
        *,
        organization_id: int,
        user_id: int,
        action: AuditAction,
        entity: str,
        entity_id: int | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        device: str | None = None,
        correlation_id: str | None = None,
        reason: str | None = None,
        before_state: dict | None = None,
        after_state: dict | None = None,
        metadata: dict | None = None,
    ) -> AuditLog:
        context = current_audit_context()
        entry = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action=action.value,
            entity=entity,
            entity_id=entity_id,
            ip_address=ip_address or context.ip_address,
            user_agent=user_agent or context.user_agent,
            device=device or context.device,
            correlation_id=correlation_id or context.correlation_id,
            reason=reason,
            before_state=redact_sensitive(before_state),
            after_state=redact_sensitive(after_state),
            metadata_json=redact_sensitive(metadata),
        )
        self.db.add(entry)
        self.db.flush()
        return entry
