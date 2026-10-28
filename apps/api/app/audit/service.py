"""Compatibility import for the Governance-owned audit writer."""

from app.governance.audit.service import AuditService, redact_sensitive

__all__ = ["AuditService", "redact_sensitive"]
