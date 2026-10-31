from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SubmissionMethod = Literal["api", "sftp", "email", "portal", "manual"]
ApprovalStatus = Literal["draft", "pending_approval", "approved", "rejected"]
HealthStatus = Literal["not_configured", "healthy", "unhealthy"]
StatusMethod = Literal["api", "portal", "email", "manual"]
PaymentMethod = Literal[
    "api",
    "sftp",
    "email",
    "portal_export",
    "csv",
    "excel",
    "report",
    "manual",
]
PolicySourceType = Literal[
    "payer_contract",
    "benefit_schedule",
    "operating_guidance",
    "clinical_guideline",
    "regulation",
]
PolicySourceStatus = Literal[
    "draft",
    "pending_approval",
    "approved",
    "rejected",
    "retired",
]


class PayerConfiguration(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    payer_code: str = Field(min_length=2, max_length=50)
    country: str = Field(default="KE", min_length=2, max_length=2)
    submission_method: SubmissionMethod = "manual"
    status_method: StatusMethod = "manual"
    payment_method: PaymentMethod = "report"
    portal_url: str | None = Field(default=None, max_length=2048)
    api_url: str | None = Field(default=None, max_length=2048)
    submission_email: str | None = Field(default=None, max_length=320)
    supports_api: bool = False
    supports_sftp: bool = False
    supports_email: bool = False
    supports_manual: bool = True
    connector_name: str | None = Field(default=None, max_length=50)
    integration_id: int | None = None
    is_active: bool = True

    @model_validator(mode="after")
    def validate_method_configuration(self):
        if self.submission_method == "api" and not self.supports_api:
            raise ValueError("API submission requires supports_api")
        if self.submission_method == "sftp" and not self.supports_sftp:
            raise ValueError("SFTP submission requires supports_sftp")
        if self.submission_method == "email" and not self.supports_email:
            raise ValueError("Email submission requires supports_email")
        if self.submission_method == "email" and not self.submission_email:
            raise ValueError("Email submission requires submission_email")
        if self.submission_method == "portal" and not self.portal_url:
            raise ValueError("Portal submission requires portal_url")
        if self.submission_method in {"api", "sftp"} and not self.connector_name:
            raise ValueError(f"{self.submission_method.upper()} submission requires connector_name")
        return self


class PayerCreate(PayerConfiguration):
    reason: str = Field(min_length=3, max_length=500)


class PayerUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=255)
    payer_code: str | None = Field(default=None, min_length=2, max_length=50)
    country: str | None = Field(default=None, min_length=2, max_length=2)
    submission_method: SubmissionMethod | None = None
    status_method: StatusMethod | None = None
    payment_method: PaymentMethod | None = None
    portal_url: str | None = Field(default=None, max_length=2048)
    api_url: str | None = Field(default=None, max_length=2048)
    submission_email: str | None = Field(default=None, max_length=320)
    supports_api: bool | None = None
    supports_sftp: bool | None = None
    supports_email: bool | None = None
    supports_manual: bool | None = None
    connector_name: str | None = Field(default=None, max_length=50)
    integration_id: int | None = None
    is_active: bool | None = None
    reason: str = Field(min_length=3, max_length=500)


class PayerRead(PayerConfiguration):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    approval_status: ApprovalStatus
    submitted_by: int | None = None
    submitted_at: datetime | None = None
    approved_by: int | None = None
    approved_at: datetime | None = None
    rejected_by: int | None = None
    rejected_at: datetime | None = None
    rejection_reason: str | None = None
    last_health_checked_at: datetime | None = None
    last_health_status: HealthStatus | None = None
    last_health_error: str | None = None
    health_check_failure_count: int = 0


class PayerRejection(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class PayerHealthCheckResult(BaseModel):
    payer_id: int
    status: HealthStatus
    checked_at: datetime
    error: str | None = None
    failure_count: int
    latency_ms: float | None = None


class PolicySourceCreate(BaseModel):
    policy_code: str = Field(min_length=2, max_length=80)
    title: str = Field(min_length=3, max_length=255)
    source_type: PolicySourceType
    jurisdiction: str = Field(default="KE", min_length=2, max_length=2)
    source_reference: str = Field(min_length=3, max_length=500)
    source_uri: str | None = Field(default=None, max_length=2048)
    content: str = Field(min_length=20, max_length=20_000)
    effective_from: date
    effective_to: date | None = None
    denial_categories: list[str] = Field(default_factory=list, max_length=25)
    procedure_codes: list[str] = Field(default_factory=list, max_length=100)
    reason: str = Field(min_length=3, max_length=500)

    @model_validator(mode="after")
    def validate_effective_dates(self):
        if self.jurisdiction.upper() != "KE":
            raise ValueError("Atlas v1 policy sources must use Kenya jurisdiction 'KE'")
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("effective_to cannot be earlier than effective_from")
        return self


class PolicySourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    payer_id: int
    policy_code: str
    title: str
    source_type: PolicySourceType
    jurisdiction: str
    version: int
    status: PolicySourceStatus
    source_reference: str
    source_uri: str | None = None
    content: str
    content_sha256: str
    effective_from: date
    effective_to: date | None = None
    denial_categories: list[str]
    procedure_codes: list[str]
    created_by: int
    change_reason: str
    submitted_by: int | None = None
    submitted_at: datetime | None = None
    approved_by: int | None = None
    approved_at: datetime | None = None
    rejected_by: int | None = None
    rejected_at: datetime | None = None
    rejection_reason: str | None = None
    created_at: datetime | None = None


class PolicySourceRejection(BaseModel):
    reason: str = Field(min_length=3, max_length=500)
