from datetime import datetime
from decimal import Decimal
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class AISettings(BaseModel):
    provider: str = Field(default="openai", min_length=1, max_length=50)
    model: str = Field(default="gpt-5", min_length=1, max_length=100)
    temperature: float = Field(default=0.2, ge=0, le=2)
    prompt_version: str = Field(default="v1", min_length=1, max_length=50)


class WorkflowSettings(BaseModel):
    auto_analyze: bool = False
    auto_appeal: bool = False
    require_approval: Literal[True] = True


class SubmissionSettings(BaseModel):
    connector: str | None = Field(default=None, max_length=50)
    retry_count: int = Field(default=3, ge=0, le=20)
    polling_interval_seconds: int = Field(default=300, ge=30, le=86400)


class BillingSettings(BaseModel):
    success_fee_percentage: Decimal = Field(default=Decimal(0), ge=0, le=100)
    currency: str = Field(default="KES", min_length=3, max_length=3)
    vat_percentage: Decimal = Field(default=Decimal(0), ge=0, le=100)
    payment_terms_days: int = Field(default=30, ge=0, le=365)
    dispute_period_days: int = Field(default=0, ge=0, le=365)
    invoice_frequency: Literal["monthly", "quarterly"] = "monthly"

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()


class BrandingSettings(BaseModel):
    logo_document_id: int | None = Field(default=None, gt=0)
    letterhead_document_id: int | None = Field(default=None, gt=0)
    signature_document_id: int | None = Field(default=None, gt=0)
    primary_color: str = Field(default="#174A5C", pattern=r"^#[0-9A-Fa-f]{6}$")


class FeatureSettings(BaseModel):
    ai_analysis: bool = True
    ai_appeal: bool = True
    payment_tracking: bool = True
    analytics: bool = True
    copilot: bool = True
    portal_automation: bool = False


class TaskIntelligenceSettings(BaseModel):
    auto_create_tasks: bool = True
    auto_assign_tasks: bool = True
    default_sla_days: int = Field(default=3, ge=1, le=365)
    payer_sla_days: dict[str, int] = Field(
        default_factory=lambda: {"SHA": 35, "JUBILEE": 21, "BRITAM": 18}
    )
    payer_skill_map: dict[str, str] = Field(
        default_factory=lambda: {
            "SHA": "sha",
            "JUBILEE": "private_insurance",
            "BRITAM": "private_insurance",
        }
    )
    high_value_threshold: Decimal = Field(default=Decimal("2000000"), ge=0)
    escalation_after_days: list[int] = Field(default_factory=lambda: [0, 14, 29])

    @field_validator("payer_sla_days")
    @classmethod
    def validate_payer_slas(cls, value: dict[str, int]) -> dict[str, int]:
        if any(days < 1 or days > 365 for days in value.values()):
            raise ValueError("payer SLA days must be between 1 and 365")
        return {key.upper(): days for key, days in value.items()}

    @field_validator("escalation_after_days")
    @classmethod
    def validate_escalations(cls, value: list[int]) -> list[int]:
        if (
            not value
            or len(value) > 3
            or value != sorted(set(value))
            or any(days < 0 for days in value)
        ):
            raise ValueError(
                "escalation days must contain one to three unique ascending non-negative values"
            )
        return value


class OrganizationSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ai: AISettings = Field(default_factory=AISettings)
    workflow: WorkflowSettings = Field(default_factory=WorkflowSettings)
    submission: SubmissionSettings = Field(default_factory=SubmissionSettings)
    billing: BillingSettings = Field(default_factory=BillingSettings)
    branding: BrandingSettings = Field(default_factory=BrandingSettings)
    features: FeatureSettings = Field(default_factory=FeatureSettings)
    task_intelligence: TaskIntelligenceSettings = Field(default_factory=TaskIntelligenceSettings)


class OrganizationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2, max_length=255)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=50)
    country: str | None = Field(default="KE", min_length=2, max_length=100)
    timezone: str = "Africa/Nairobi"
    currency: str = Field(default="KES", min_length=3, max_length=3)
    billing_email: EmailStr | None = None
    subscription_plan: str = Field(default="trial", min_length=1, max_length=50)
    settings: OrganizationSettings = Field(default_factory=OrganizationSettings)

    @field_validator("currency")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return value.upper() if value else value

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("timezone must be a valid IANA timezone") from exc
        return value


class OrganizationProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=2, max_length=255)
    country: str | None = Field(default=None, min_length=2, max_length=100)
    timezone: str | None = None
    billing_email: EmailStr | None = None
    status: Literal["pending_verification", "active", "suspended"] | None = None
    reason: str = Field(min_length=3, max_length=500)

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("timezone must be a valid IANA timezone") from exc
        return value


class OrganizationSettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    settings: OrganizationSettings
    reason: str = Field(min_length=3, max_length=500)


class OrganizationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str | None
    country: str | None
    timezone: str
    currency: str
    subscription_plan: str
    success_fee_percentage: Decimal
    email: EmailStr
    billing_email: EmailStr | None
    phone: str | None
    status: str
    is_active: bool
    settings: OrganizationSettings
    created_at: datetime
    updated_at: datetime


class OrganizationSettingsResponse(BaseModel):
    organization_id: int
    version: int
    settings: OrganizationSettings


class OrganizationSettingsVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    version: int
    settings: OrganizationSettings
    changed_by: int
    reason: str
    correlation_id: str
    created_at: datetime
