from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SHADiagnosisMapping(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_diagnosis_id: int = Field(gt=0)
    icd11_code: str = Field(min_length=1, max_length=20)
    display: str = Field(min_length=1, max_length=255)


class SHALineMapping(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_line_id: int = Field(gt=0)
    intervention_code: str = Field(min_length=1, max_length=50)
    intervention_display: str = Field(min_length=1, max_length=255)
    benefit_category_code: str = Field(min_length=1, max_length=20)
    benefit_category_display: str = Field(min_length=1, max_length=100)


class SHAPatientContact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    family_name: str = Field(min_length=1, max_length=100)
    given_names: list[str] = Field(min_length=1, max_length=5)
    phone: str = Field(min_length=7, max_length=30)


class SHAPractitionerInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    identifier_type: Literal["SHA-NUMBER", "NATIONAL-ID"]
    identifier: str = Field(min_length=1, max_length=100)
    family_name: str = Field(min_length=1, max_length=100)
    given_names: list[str] = Field(min_length=1, max_length=5)
    phone: str = Field(min_length=7, max_length=30)
    gender: Literal["male", "female", "other", "unknown"]
    birth_date: date


class SHAInvoiceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    number: str = Field(min_length=1, max_length=100)
    date: date
    patient_share: Decimal = Field(ge=0, max_digits=12, decimal_places=2)


class SHACoverageInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    number: str = Field(min_length=1, max_length=100)
    class_code: str = Field(min_length=1, max_length=50)
    class_display: str = Field(min_length=1, max_length=100)
    class_value: str = Field(min_length=1, max_length=100)
    class_name: str = Field(min_length=1, max_length=255)
    annual_limit_category_code: str = Field(min_length=1, max_length=30)
    annual_limit_category_display: str = Field(min_length=1, max_length=100)
    period_start: date | None = None
    period_end: date | None = None

    @model_validator(mode="after")
    def validate_period(self):
        if self.period_start and self.period_end and self.period_end < self.period_start:
            raise ValueError("coverage period_end must be on or after period_start")
        return self


class SHAEncounterInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    number: str = Field(min_length=1, max_length=100)
    class_code: Literal["AMB", "EMER", "IMP", "HH", "VR"]
    class_display: str = Field(min_length=1, max_length=100)
    service_type_code: str = Field(min_length=1, max_length=30)
    service_type_display: str = Field(min_length=1, max_length=100)
    period_start: datetime
    period_end: datetime

    @model_validator(mode="after")
    def validate_period(self):
        if self.period_end < self.period_start:
            raise ValueError("encounter period_end must be on or after period_start")
        return self


class SHAClaimSubmit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    integration_id: int = Field(gt=0)
    idempotency_key: str = Field(min_length=8, max_length=100, pattern=r"^[A-Za-z0-9._:-]+$")
    reason: str = Field(min_length=3, max_length=500)
    patient_identifier_type: Literal["SHA-NUMBER", "NATIONAL-ID"]
    patient_identifier: str = Field(min_length=1, max_length=100)
    patient_gender: Literal["male", "female", "other", "unknown"]
    patient_phone: str = Field(min_length=7, max_length=30)
    patient_contact: SHAPatientContact
    practitioner: SHAPractitionerInput
    invoice: SHAInvoiceInput
    claim_type: Literal["institutional", "professional", "oral", "pharmacy", "vision"]
    claim_subtype: Literal[
        "day-case", "rehabilitation", "inpatient", "outpatient", "emergency"
    ]
    coverage: SHACoverageInput
    encounter: SHAEncounterInput
    diagnoses: list[SHADiagnosisMapping] = Field(min_length=1)
    line_items: list[SHALineMapping] = Field(min_length=1)


class SHAExchangeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    claim_id: int
    integration_id: int
    initiated_by: int
    idempotency_key: str
    correlation_id: str
    reason: str
    ig_version: str
    bundle_identifier: str
    bundle_sha256: str
    status: str
    external_reference: str | None
    claim_response_id: str | None
    outcome: str | None
    workflow_state: str | None
    approved_amount: Decimal | None
    currency: str | None
    response_sha256: str | None
    last_http_status: int | None
    response_summary: dict | None
    error_code: str | None
    error_summary: str | None
    requested_at: datetime
    submitted_at: datetime | None
    last_checked_at: datetime | None
    created_at: datetime
    updated_at: datetime


class SHAExchangeRefresh(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=3, max_length=500)
