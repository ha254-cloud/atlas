from uuid import uuid4

from sqlalchemy.orm import Session

from app.audit.actions import AuditAction
from app.audit.service import AuditService
from app.integrations.contracts import (
    CredentialContract,
    credential_fingerprints,
    credential_storage_values,
    validate_provider_credentials,
)
from app.integrations.encryption import encrypt_token
from app.integrations.repository import IntegrationRepository
from app.models.integration import Integration, IntegrationCredentialVersion, IntegrationStatus


class IntegrationService:
    def __init__(self, db: Session, organization_id: int):
        self.db = db
        self.organization_id = organization_id
        self.repository = IntegrationRepository(db, organization_id)

    def get(self, integration_id: int) -> Integration:
        row = self.repository.get(integration_id)
        if row is None:
            raise ValueError("Integration not found")
        return row

    def create(
        self,
        *,
        provider: str,
        settings: dict | None,
        credentials: CredentialContract | None,
        actor_id: int,
        correlation_id: str | None,
        ip_address: str | None,
    ) -> Integration:
        row = Integration(
            organization_id=self.organization_id,
            provider=provider.lower(),
            status=IntegrationStatus.PENDING,
            settings=settings,
        )
        self.db.add(row)
        self.db.flush()
        if credentials:
            self._set_credentials(
                row,
                credentials,
                actor_id=actor_id,
                reason="Initial credential configuration",
                correlation_id=correlation_id,
            )
        AuditService(self.db).log(
            organization_id=self.organization_id,
            user_id=actor_id,
            action=AuditAction.INTEGRATION_CONNECTED,
            entity="integration",
            entity_id=row.id,
            ip_address=ip_address,
            metadata={
                "provider": row.provider,
                "correlation_id": correlation_id,
                "credential_kind": credentials.kind if credentials else None,
            },
        )
        self.db.commit()
        self.db.refresh(row)
        return row

    def rotate_credentials(
        self,
        integration_id: int,
        credentials: CredentialContract,
        *,
        actor_id: int,
        reason: str,
        correlation_id: str | None,
        ip_address: str | None,
    ) -> IntegrationCredentialVersion:
        row = self.get(integration_id)
        request_id = correlation_id or str(uuid4())
        before = self._current_fingerprints(row)
        version = self._set_credentials(
            row,
            credentials,
            actor_id=actor_id,
            reason=reason,
            correlation_id=request_id,
        )
        row.status = IntegrationStatus.PENDING
        row.last_error = None
        AuditService(self.db).log(
            organization_id=self.organization_id,
            user_id=actor_id,
            action=AuditAction.INTEGRATION_CREDENTIALS_ROTATED,
            entity="integration",
            entity_id=row.id,
            ip_address=ip_address,
            metadata={
                "before": before,
                "after": version.fingerprints,
                "reason": reason.strip(),
                "correlation_id": request_id,
                "credential_kind": version.credential_kind,
            },
        )
        self.db.commit()
        self.db.refresh(version)
        return version

    def list_credential_versions(
        self,
        integration_id: int,
    ) -> list[IntegrationCredentialVersion]:
        self.get(integration_id)
        return self.repository.list_credential_versions(integration_id)

    def _set_credentials(
        self,
        row: Integration,
        credentials: CredentialContract,
        *,
        actor_id: int,
        reason: str,
        correlation_id: str | None,
    ) -> IntegrationCredentialVersion:
        validate_provider_credentials(row.provider, credentials)
        primary, secondary, expires_at = credential_storage_values(credentials)
        row.encrypted_access_token = encrypt_token(primary) if primary else None
        row.encrypted_refresh_token = encrypt_token(secondary) if secondary else None
        row.token_expires_at = expires_at
        version = IntegrationCredentialVersion(
            integration_id=row.id,
            version=self.repository.next_credential_version(row.id),
            credential_kind=credentials.kind,
            fingerprints=credential_fingerprints(credentials),
            expires_at=expires_at,
            changed_by=actor_id,
            reason=reason.strip(),
            correlation_id=correlation_id or str(uuid4()),
        )
        self.db.add(version)
        self.db.flush()
        return version

    @staticmethod
    def _current_fingerprints(row: Integration) -> dict[str, str]:
        from app.integrations.encryption import decrypt_token

        values = []
        for encrypted in (row.encrypted_access_token, row.encrypted_refresh_token):
            values.append(decrypt_token(encrypted) if encrypted else None)
        from hashlib import sha256

        return {
            name: sha256(value.encode()).hexdigest()[:16]
            for name, value in zip(("primary", "secondary"), values, strict=True)
            if value
        }
