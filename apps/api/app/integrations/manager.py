import asyncio
import time
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.config import settings
from app.integrations.contracts import PROVIDER_CREDENTIAL_KINDS
from app.integrations.encryption import decrypt_token
from app.integrations.exceptions import AuthenticationError, IntegrationError, SyncError
from app.integrations.models import SyncResult
from app.integrations.registry import registry
from app.models.integration import Integration, IntegrationStatus
from app.observability.logging import get_logger
from app.observability.metrics import metrics


logger = get_logger("atlas.integrations")


class IntegrationManager:
    """
    Orchestrates the full sync lifecycle for one integration:

        Connector  →  Authenticate  →  Sync  →  Normalize  →  Import

    The manager is the only component that touches the Integration DB row.
    It delegates data fetching to the connector and data persistence to the
    import pipeline — keeping each layer responsible for exactly one thing.
    """

    def __init__(self, db: Session):
        self.db = db

    def get_integration(self, integration_id: int, organization_id: int) -> Integration:
        row = (
            self.db.query(Integration)
            .filter(
                Integration.id == integration_id,
                Integration.organization_id == organization_id,
            )
            .first()
        )
        if row is None:
            raise IntegrationError(f"Integration {integration_id} not found")
        return row

    async def sync(
        self,
        integration_id: int,
        organization_id: int,
    ) -> SyncResult:
        """
        Run a full sync for an integration.
        Marks the integration as syncing, runs the connector, then
        updates the DB record with the result.
        """
        row = self.get_integration(integration_id, organization_id)
        self._ensure_credentials_not_expired(row)

        # Resolve and instantiate the connector with decrypted credentials
        config = self._build_config(row)
        connector = registry.get(row.provider, **config)

        # Mark as syncing
        row.status = IntegrationStatus.SYNCING
        self.db.commit()

        result = SyncResult(provider=row.provider, organization_id=organization_id)

        try:
            await connector.authenticate()

            result.claims = await connector.sync_claims()
            result.patients = await connector.sync_patients()
            result.payments = await connector.sync_payments()

            row.status = IntegrationStatus.ACTIVE
            row.last_error = None
        except Exception as exc:
            result.errors.append(str(exc))
            row.status = IntegrationStatus.ERROR
            row.last_error = str(exc)
            raise SyncError(f"Sync failed for integration {integration_id}: {exc}") from exc
        finally:
            from datetime import datetime
            row.last_sync_at = datetime.utcnow()
            self.db.commit()

        return result

    async def health_check(
        self,
        integration_id: int,
        organization_id: int,
        correlation_id: str | None = None,
    ) -> dict:
        row = self.get_integration(integration_id, organization_id)
        self._ensure_credentials_not_expired(row)
        config = self._build_config(row)
        started = time.monotonic()
        attempts = settings.INTEGRATION_HEALTH_RETRIES + 1
        try:
            for attempt in range(1, attempts + 1):
                connector = registry.get(row.provider, **config)
                try:
                    async with asyncio.timeout(settings.INTEGRATION_HEALTH_TIMEOUT_SECONDS):
                        await connector.authenticate()
                        result = await connector.health_check()
                    result["attempts"] = attempt
                    return result
                except Exception as exc:
                    if attempt == attempts:
                        raise IntegrationError(
                            f"Health check failed after {attempts} attempt(s): {exc}"
                        ) from exc
        finally:
            latency_ms = round((time.monotonic() - started) * 1000, 2)
            metrics.record_timing("integration.health_check_latency_ms", latency_ms)
            logger.info(
                "integration_health_check",
                extra={
                    "organization_id": organization_id,
                    "integration_id": integration_id,
                    "provider": row.provider,
                    "correlation_id": correlation_id,
                    "latency_ms": latency_ms,
                },
            )

    def _build_config(self, row: Integration) -> dict:
        """Decrypt stored tokens and build the config dict for the connector."""
        config: dict = {"organization_id": row.organization_id}

        if row.encrypted_access_token:
            primary = decrypt_token(row.encrypted_access_token)
            if PROVIDER_CREDENTIAL_KINDS.get(row.provider) == "api_key":
                config["api_key"] = primary
            else:
                config["access_token"] = primary

        if row.encrypted_refresh_token:
            config["refresh_token"] = decrypt_token(row.encrypted_refresh_token)

        if row.settings:
            config.update(row.settings)

        return config

    @staticmethod
    def _ensure_credentials_not_expired(row: Integration) -> None:
        expires_at = row.token_expires_at
        if expires_at is None:
            return
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at <= datetime.now(UTC):
            raise AuthenticationError(
                "Integration credentials have expired; rotate them before use"
            )
