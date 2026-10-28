"""Payer connectivity monitoring.

A payer that submits/polls through a bound `Integration` connector reuses
the same live health check that powers the Integration Health Dashboard
(`IntegrationManager.health_check`) rather than re-implementing connector
probing here. Payers with no `integration_id` (manual, portal, or email
submission methods) are reported as "not_configured" — there is nothing to
monitor because no connector is registered for them.
"""

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.integrations.exceptions import ConnectorNotFoundError, IntegrationError
from app.integrations.manager import IntegrationManager
from app.observability.logging import get_logger
from app.payers.models import Payer
from app.payers.repository import PayerRepository

logger = get_logger("atlas.payers")


@dataclass
class PayerHealthCheckOutcome:
    """Result of a single health check, pairing the persisted `Payer` state
    with the point-in-time latency (not itself persisted on the model)."""

    payer: Payer
    latency_ms: float | None


class PayerMonitoringService:
    def __init__(self, db: Session, organization_id: int):
        self.db = db
        self.organization_id = organization_id
        self.repository = PayerRepository(db, organization_id)

    async def check_health(
        self, payer_id: int, *, correlation_id: str | None = None
    ) -> PayerHealthCheckOutcome:
        payer = self.repository.get(payer_id)
        if payer is None:
            raise ValueError("Payer not found")

        status: str
        error: str | None
        latency_ms: float | None = None

        if payer.integration_id is None:
            status, error = "not_configured", None
        else:
            try:
                result = await IntegrationManager(self.db).health_check(
                    payer.integration_id,
                    self.organization_id,
                    correlation_id=correlation_id,
                )
                latency_ms = result.get("latency_ms")
                status = "healthy" if result.get("connected") else "unhealthy"
                error = None if status == "healthy" else "Integration reported a disconnected state"
            except (IntegrationError, ConnectorNotFoundError) as exc:
                status, error = "unhealthy", str(exc)

        self._record(payer, status=status, error=error)
        logger.info(
            "payer_health_check",
            extra={
                "organization_id": self.organization_id,
                "payer_id": payer.id,
                "integration_id": payer.integration_id,
                "status": status,
                "correlation_id": correlation_id,
                "latency_ms": latency_ms,
            },
        )
        return PayerHealthCheckOutcome(payer=payer, latency_ms=latency_ms)

    def _record(self, payer: Payer, *, status: str, error: str | None) -> None:
        payer.last_health_checked_at = datetime.now(UTC)
        payer.last_health_status = status
        payer.last_health_error = error
        payer.health_check_failure_count = (
            0 if status in {"healthy", "not_configured"} else payer.health_check_failure_count + 1
        )
        self.db.commit()
        self.db.refresh(payer)
