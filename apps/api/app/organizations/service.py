from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from app.audit.actions import AuditAction
from app.audit.service import AuditService
from app.billing.service import RecoveryFeeScheduleService
from app.organizations.models import Organization, OrganizationSettingsVersion
from app.organizations.repository import OrganizationRepository
from app.organizations.schemas import (
    OrganizationCreate,
    OrganizationProfileUpdate,
    OrganizationSettings,
    OrganizationSettingsUpdate,
)
from app.security.slug import unique_organization_slug


class OrganizationService:
    def __init__(self, db: Session, organization_id: int | None = None) -> None:
        self.db = db
        self.organization_id = organization_id
        self.repository = OrganizationRepository(db, organization_id)

    def create(self, data: OrganizationCreate) -> Organization:
        if self.repository.get_by_email(str(data.email)) is not None:
            raise ValueError("Organization with this email already exists")
        settings = data.settings.model_dump(mode="json")
        organization = Organization(
            name=data.name.strip(),
            slug=unique_organization_slug(self.db, data.name),
            country=data.country,
            timezone=data.timezone,
            currency=data.settings.billing.currency,
            subscription_plan=data.subscription_plan,
            success_fee_percentage=data.settings.billing.success_fee_percentage,
            billing_email=str(data.billing_email or data.email),
            email=str(data.email),
            phone=data.phone,
            settings=settings,
        )
        self.repository.create(organization)
        self.db.commit()
        self.db.refresh(organization)
        return organization

    def get(self) -> Organization:
        organization = self.repository.get()
        if organization is None:
            raise ValueError("Organization not found")
        return organization

    def get_by_id(self, organization_id: int) -> Organization | None:
        if self.organization_id is not None and organization_id != self.organization_id:
            return None
        return self.repository.get_by_id(organization_id)

    def settings(self) -> OrganizationSettings:
        return OrganizationSettings.model_validate(self.get().settings or {})

    def settings_version(self) -> int:
        return self.repository.next_settings_version() - 1

    def update_profile(
        self,
        payload: OrganizationProfileUpdate,
        *,
        actor_id: int,
        correlation_id: str | None,
        ip_address: str | None,
        user_agent: str | None,
    ) -> Organization:
        organization = self.get()
        before = self._profile_snapshot(organization)
        changes = payload.model_dump(exclude={"reason"}, exclude_none=True)
        for field, value in changes.items():
            setattr(organization, field, value)
        if payload.status is not None:
            organization.is_active = payload.status == "active"
        after = self._profile_snapshot(organization)
        self._audit(
            actor_id=actor_id,
            action=AuditAction.ORGANIZATION_UPDATED,
            organization=organization,
            before=before,
            after=after,
            reason=payload.reason,
            correlation_id=correlation_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self.db.commit()
        self.db.refresh(organization)
        return organization

    def update_settings(
        self,
        payload: OrganizationSettingsUpdate,
        *,
        actor_id: int,
        correlation_id: str | None,
        ip_address: str | None,
        user_agent: str | None,
    ) -> OrganizationSettingsVersion:
        organization = self.get()
        before = self.settings().model_dump(mode="json")
        after = payload.settings.model_dump(mode="json")
        request_id = correlation_id or str(uuid4())
        version = OrganizationSettingsVersion(
            organization_id=organization.id,
            version=self.repository.next_settings_version(),
            settings=after,
            changed_by=actor_id,
            reason=payload.reason.strip(),
            correlation_id=request_id,
        )
        organization.settings = after
        organization.success_fee_percentage = payload.settings.billing.success_fee_percentage
        organization.currency = payload.settings.billing.currency
        self.repository.add_settings_version(version)
        self.db.flush()
        self._sync_fee_schedule(
            payload.settings,
            actor_id=actor_id,
            reason=payload.reason,
        )
        self._audit(
            actor_id=actor_id,
            action=AuditAction.ORGANIZATION_SETTINGS_UPDATED,
            organization=organization,
            before=before,
            after=after,
            reason=payload.reason,
            correlation_id=request_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self.db.commit()
        self.db.refresh(version)
        return version

    def _sync_fee_schedule(
        self,
        settings: OrganizationSettings,
        *,
        actor_id: int,
        reason: str,
    ) -> None:
        billing = settings.billing
        fee_service = RecoveryFeeScheduleService(self.db, self.organization_id)
        effective_date = datetime.now(UTC).date()
        try:
            current = fee_service.effective_on(effective_date)
        except ValueError:
            current = None
        desired = (
            billing.success_fee_percentage,
            billing.vat_percentage,
            billing.currency,
            billing.payment_terms_days,
            billing.dispute_period_days,
        )
        existing = (
            (
                current.fee_percentage,
                current.vat_percentage,
                current.currency,
                current.payment_terms_days,
                current.dispute_period_days,
            )
            if current
            else None
        )
        if desired == existing:
            return
        fee_service.create(
            fee_percentage=billing.success_fee_percentage,
            vat_percentage=billing.vat_percentage,
            currency=billing.currency,
            payment_terms_days=billing.payment_terms_days,
            dispute_period_days=billing.dispute_period_days,
            effective_from=effective_date,
            effective_to=None,
            created_by=actor_id,
            reason=reason,
        )

    def list_settings_versions(self) -> list[OrganizationSettingsVersion]:
        self.get()
        return self.repository.list_settings_versions()

    def _audit(
        self,
        *,
        actor_id: int,
        action: AuditAction,
        organization: Organization,
        before: dict[str, Any],
        after: dict[str, Any],
        reason: str,
        correlation_id: str | None,
        ip_address: str | None,
        user_agent: str | None,
    ) -> None:
        AuditService(self.db).log(
            organization_id=organization.id,
            user_id=actor_id,
            action=action,
            entity="organization",
            entity_id=organization.id,
            ip_address=ip_address,
            metadata={
                "before": before,
                "after": after,
                "reason": reason.strip(),
                "correlation_id": correlation_id,
                "user_agent": user_agent,
            },
        )

    @staticmethod
    def _profile_snapshot(organization: Organization) -> dict[str, Any]:
        return {
            "name": organization.name,
            "country": organization.country,
            "timezone": organization.timezone,
            "billing_email": organization.billing_email,
            "status": organization.status,
            "is_active": organization.is_active,
        }
