from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SubmissionMethod = Literal["api", "sftp", "email", "portal", "manual"]
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
