from typing import Any

from sqlalchemy.orm import Session

import app.integrations.mock  # noqa: F401
from app.audit.actions import AuditAction
from app.audit.service import AuditService
from app.integrations.exceptions import IntegrationError
from app.integrations.manager import IntegrationManager
from app.integrations.registry import submission_registry
from app.payers.models import Payer
from app.payers.repository import PayerRepository
from app.payers.schemas import PayerConfiguration, PayerCreate, PayerUpdate


class PayerService:
    def __init__(self, db: Session, organization_id: int):
        self.db = db
        self.organization_id = organization_id
        self.repository = PayerRepository(db, organization_id)

    def list(self, *, active_only: bool = True) -> list[Payer]:
        return self.repository.list(active_only=active_only)

    def get(self, payer_id: int) -> Payer:
        payer = self.repository.get(payer_id)
        if payer is None:
            raise ValueError("Payer not found")
        return payer

    def create(
        self,
        payload: PayerCreate,
        *,
        actor_id: int,
        correlation_id: str | None,
        ip_address: str | None,
    ) -> Payer:
        code = payload.payer_code.strip().upper()
        if self.repository.get_by_code(code):
            raise ValueError(f"Payer code '{code}' already exists")
        values = payload.model_dump(exclude={"reason"})
        values["name"] = payload.name.strip()
        values["payer_code"] = code
        values["country"] = payload.country.upper()
        self._validate_binding(values)
        payer = Payer(organization_id=self.organization_id, **values)
        self.db.add(payer)
        self.db.flush()
        self._audit(
            payer,
            actor_id=actor_id,
            action=AuditAction.PAYER_CREATED,
            before=None,
            after=self._snapshot(payer),
            reason=payload.reason,
            correlation_id=correlation_id,
            ip_address=ip_address,
        )
        self.db.commit()
        self.db.refresh(payer)
        return payer

    def update(
        self,
        payer_id: int,
        payload: PayerUpdate,
        *,
        actor_id: int,
        correlation_id: str | None,
        ip_address: str | None,
    ) -> Payer:
        payer = self.get(payer_id)
        before = self._snapshot(payer)
        updates = payload.model_dump(exclude={"reason"}, exclude_unset=True)
        if "payer_code" in updates:
            updates["payer_code"] = updates["payer_code"].strip().upper()
            duplicate = self.repository.get_by_code(updates["payer_code"])
            if duplicate and duplicate.id != payer.id:
                raise ValueError(f"Payer code '{updates['payer_code']}' already exists")
        if "country" in updates:
            updates["country"] = updates["country"].upper()
        candidate = {**before, **updates}
        PayerConfiguration.model_validate(candidate)
        self._validate_binding(candidate)
        for field, value in updates.items():
            setattr(payer, field, value)
        self._audit(
            payer,
            actor_id=actor_id,
            action=AuditAction.PAYER_UPDATED,
            before=before,
            after=self._snapshot(payer),
            reason=payload.reason,
            correlation_id=correlation_id,
            ip_address=ip_address,
        )
        self.db.commit()
        self.db.refresh(payer)
        return payer

    def _validate_binding(self, values: dict[str, Any]) -> None:
        integration_id = values.get("integration_id")
        connector_name = values.get("connector_name")
        if integration_id is not None:
            try:
                IntegrationManager(self.db).get_integration(
                    integration_id,
                    self.organization_id,
                )
            except IntegrationError as exc:
                raise ValueError("Integration not found") from exc
        if connector_name and connector_name not in submission_registry.list_providers():
            raise ValueError(f"Submission connector '{connector_name}' is not registered")
        if values.get("submission_method") in {"api", "sftp"} and integration_id is None:
            raise ValueError("API and SFTP submission methods require integration_id")

    def _audit(
        self,
        payer: Payer,
        *,
        actor_id: int,
        action: AuditAction,
        before: dict[str, Any] | None,
        after: dict[str, Any],
        reason: str,
        correlation_id: str | None,
        ip_address: str | None,
    ) -> None:
        AuditService(self.db).log(
            organization_id=self.organization_id,
            user_id=actor_id,
            action=action,
            entity="payer",
            entity_id=payer.id,
            ip_address=ip_address,
            metadata={
                "before": before,
                "after": after,
                "reason": reason.strip(),
                "correlation_id": correlation_id,
            },
        )

    @staticmethod
    def _snapshot(payer: Payer) -> dict[str, Any]:
        return {
            "name": payer.name,
            "payer_code": payer.payer_code,
            "country": payer.country,
            "submission_method": payer.submission_method,
            "status_method": payer.status_method,
            "payment_method": payer.payment_method,
            "portal_url": payer.portal_url,
            "api_url": payer.api_url,
            "submission_email": payer.submission_email,
            "supports_api": payer.supports_api,
            "supports_sftp": payer.supports_sftp,
            "supports_email": payer.supports_email,
            "supports_manual": payer.supports_manual,
            "connector_name": payer.connector_name,
            "integration_id": payer.integration_id,
            "is_active": payer.is_active,
        }
