from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.governance.models import (
    ConsentDecision,
    ConsentPurpose,
    RetentionDisposition,
    RetentionEnforcementMode,
)


class ConsentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    purpose: ConsentPurpose
    decision: ConsentDecision
    retention_years: int | None = Field(default=None, ge=1, le=100)
    effective_at: datetime | None = None
    expires_at: datetime | None = None
    reason: str = Field(min_length=3, max_length=500)

    @model_validator(mode="after")
    def validate_retention(self):
        if self.retention_years is not None and self.purpose != ConsentPurpose.RETENTION:
            raise ValueError("retention_years is only valid for retention consent")
        return self


class ConsentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    patient_id: int
    purpose: str
    decision: str
    version: int
    retention_years: int | None
    effective_at: datetime
    expires_at: datetime | None
    recorded_by: int
    reason: str
    correlation_id: str
    created_at: datetime


class RetentionPolicyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resource_type: str = Field(pattern=r"^[a-z][a-z0-9_]{2,99}$")
    retention_days: int = Field(ge=1, le=36500)
    disposition: RetentionDisposition
    legal_hold_default: bool = False
    enforcement_mode: RetentionEnforcementMode = RetentionEnforcementMode.REPORT_ONLY
    reason: str = Field(min_length=3, max_length=500)


class RetentionPolicyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    resource_type: str
    version: int
    retention_days: int
    disposition: str
    legal_hold_default: bool
    enforcement_mode: str
    created_by: int
    reason: str
    correlation_id: str
    created_at: datetime


class SessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: int
    ip_address: str | None
    device: str | None
    location: str | None
    created_at: datetime
    last_seen_at: datetime
    expires_at: datetime
    revoked_at: datetime | None


class SessionRevoke(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=3, max_length=500)


class SecuritySummary(BaseModel):
    failed_logins_30d: int
    password_resets_30d: int
    inactive_users_90d: int
    suspicious_users: int
    active_sessions: int


class ComplianceSummary(BaseModel):
    audit_status: str
    total_audit_events: int
    missing_document_claims: int
    outstanding_approvals: int
    inactive_users: int
    ai_calls_without_prompt_version: int
    approved_appeals_without_approver: int
    consented_patients: int
    patients_without_consent: int
    configured_retention_policies: int
    retention_enforcement_mode: str
    security: SecuritySummary
