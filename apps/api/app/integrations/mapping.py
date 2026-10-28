from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.integration import (
    Integration,
    IntegrationMappingField,
    IntegrationMappingProfile,
)

CANONICAL_CLAIM_FIELDS = {
    "authorization_expiration",
    "authorization_number",
    "billed_amount",
    "branch_code",
    "claim_number",
    "denial_code",
    "denial_reason",
    "department_code",
    "diagnosis_codes",
    "medical_record_number",
    "modifiers",
    "paid_amount",
    "patient_first_name",
    "patient_last_name",
    "payer_code",
    "procedure_codes",
    "service_date",
    "status",
    "currency",
}
REQUIRED_CANONICAL_FIELDS = {
    "billed_amount",
    "claim_number",
    "payer_code",
    "service_date",
}


class MappingError(ValueError):
    def __init__(self, code: str, message: str, source_field: str | None = None):
        super().__init__(message)
        self.code = code
        self.source_field = source_field


def apply_mapping(raw: dict[str, Any], fields: list[IntegrationMappingField]) -> dict[str, Any]:
    mapped: dict[str, Any] = {}
    for field in fields:
        value = raw.get(field.source_field, field.default_value)
        if value in (None, ""):
            if field.required:
                raise MappingError(
                    "required_source_field_missing",
                    f"Required source field '{field.source_field}' is missing",
                    field.source_field,
                )
            continue
        mapped[field.target_field] = _transform(value, field.transform, field.source_field)
    return mapped


def _transform(value: Any, transform: dict | None, source_field: str) -> Any:
    if not transform:
        return value.strip() if isinstance(value, str) else value

    transform_type = transform.get("type")
    if transform_type == "text":
        text = str(value).strip()
        case = transform.get("case")
        if case == "upper":
            return text.upper()
        if case == "lower":
            return text.lower()
        return text

    if transform_type == "date":
        input_format = transform.get("input_format", "%Y-%m-%d")
        try:
            return datetime.strptime(str(value).strip(), input_format).date().isoformat()
        except ValueError as exc:
            raise MappingError(
                "invalid_date",
                f"Field '{source_field}' does not match date format {input_format}",
                source_field,
            ) from exc

    if transform_type == "decimal":
        text = str(value).strip()
        for symbol in transform.get("currency_symbols", ["KES", "KSh", ","]):
            text = text.replace(symbol, "")
        try:
            return str(Decimal(text.strip()).quantize(Decimal("0.01")))
        except InvalidOperation as exc:
            raise MappingError(
                "invalid_decimal",
                f"Field '{source_field}' is not a valid amount",
                source_field,
            ) from exc

    if transform_type == "split":
        delimiter = transform.get("delimiter", ",")
        return ",".join(part.strip() for part in str(value).split(delimiter) if part.strip())

    raise MappingError(
        "unsupported_transform",
        f"Unsupported transform '{transform_type}' for field '{source_field}'",
        source_field,
    )


class IntegrationMappingService:
    def __init__(self, db: Session, organization_id: int):
        self.db = db
        self.organization_id = organization_id

    def create_profile(
        self,
        integration_id: int,
        *,
        name: str,
        source_format: str,
        fields: list[dict],
        actor_id: int,
        reason: str,
        correlation_id: str,
    ) -> IntegrationMappingProfile:
        integration = self._integration(integration_id)
        target_fields = {field["target_field"] for field in fields}
        unknown = target_fields - CANONICAL_CLAIM_FIELDS
        if unknown:
            raise ValueError(f"Unsupported canonical fields: {', '.join(sorted(unknown))}")
        missing = REQUIRED_CANONICAL_FIELDS - target_fields
        if missing:
            raise ValueError(f"Missing required canonical mappings: {', '.join(sorted(missing))}")

        version = (
            int(
                self.db.query(func.max(IntegrationMappingProfile.version))
                .filter(IntegrationMappingProfile.integration_id == integration.id)
                .scalar()
                or 0
            )
            + 1
        )
        profile = IntegrationMappingProfile(
            organization_id=self.organization_id,
            integration_id=integration.id,
            version=version,
            name=name,
            source_format=source_format,
            created_by=actor_id,
            reason=reason,
            correlation_id=correlation_id,
        )
        self.db.add(profile)
        self.db.flush()
        self.db.add_all(
            IntegrationMappingField(
                profile_id=profile.id,
                source_field=field["source_field"],
                target_field=field["target_field"],
                transform=field.get("transform"),
                required=field.get("required", False),
                default_value=field.get("default_value"),
            )
            for field in fields
        )
        self.db.commit()
        self.db.refresh(profile)
        return profile

    def list_profiles(self, integration_id: int) -> list[IntegrationMappingProfile]:
        self._integration(integration_id)
        return (
            self.db.query(IntegrationMappingProfile)
            .filter(
                IntegrationMappingProfile.integration_id == integration_id,
                IntegrationMappingProfile.organization_id == self.organization_id,
            )
            .order_by(IntegrationMappingProfile.version.desc())
            .all()
        )

    def get_profile(self, integration_id: int, profile_id: int) -> IntegrationMappingProfile:
        self._integration(integration_id)
        profile = (
            self.db.query(IntegrationMappingProfile)
            .filter(
                IntegrationMappingProfile.id == profile_id,
                IntegrationMappingProfile.integration_id == integration_id,
                IntegrationMappingProfile.organization_id == self.organization_id,
            )
            .first()
        )
        if profile is None:
            raise ValueError("Mapping profile not found")
        return profile

    def latest_profile(self, integration_id: int) -> IntegrationMappingProfile | None:
        self._integration(integration_id)
        return (
            self.db.query(IntegrationMappingProfile)
            .filter(
                IntegrationMappingProfile.integration_id == integration_id,
                IntegrationMappingProfile.organization_id == self.organization_id,
                IntegrationMappingProfile.is_active.is_(True),
            )
            .order_by(IntegrationMappingProfile.version.desc())
            .first()
        )

    def fields_for(self, profile_id: int) -> list[IntegrationMappingField]:
        return (
            self.db.query(IntegrationMappingField)
            .join(
                IntegrationMappingProfile,
                IntegrationMappingProfile.id == IntegrationMappingField.profile_id,
            )
            .filter(
                IntegrationMappingField.profile_id == profile_id,
                IntegrationMappingProfile.organization_id == self.organization_id,
            )
            .order_by(IntegrationMappingField.id)
            .all()
        )

    def _integration(self, integration_id: int) -> Integration:
        integration = (
            self.db.query(Integration)
            .filter(
                Integration.id == integration_id,
                Integration.organization_id == self.organization_id,
            )
            .first()
        )
        if integration is None:
            raise ValueError("Integration not found")
        return integration
