from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy.orm import Session

from app.audit.actions import AuditAction
from app.audit.service import AuditService
from app.eclaims.fhir import (
    IG_VERSION,
    SHABundleBuilder,
    canonical_json_sha256,
    claim_response_summary,
)
from app.eclaims.models import SHAExchange, SHAExchangeEvent
from app.eclaims.repository import SHAExchangeRepository
from app.eclaims.schemas import SHAClaimSubmit
from app.events.event_types import EventType
from app.events.publisher import EventPublisher
from app.integrations.base import EClaimsConnector, EClaimsTransportResponse
from app.integrations.connectors.sha import SHAConnectorError
from app.integrations.manager import IntegrationManager
from app.models.integration import IntegrationStatus


class SHAExchangeService:
    def __init__(self, db: Session, organization_id: int) -> None:
        self.db = db
        self.organization_id = organization_id
        self.repository = SHAExchangeRepository(db, organization_id)

    async def submit(
        self,
        claim_id: int,
        payload: SHAClaimSubmit,
        *,
        actor_id: int,
        correlation_id: str | None,
    ) -> SHAExchange:
        existing = self.repository.by_idempotency_key(payload.idempotency_key)
        if existing is not None:
            if (
                existing.claim_id != claim_id
                or existing.integration_id != payload.integration_id
            ):
                raise ValueError(
                    "idempotency_key is already used for another claim or integration"
                )
            return existing

        claim = self.repository.claim(claim_id)
        if claim is None:
            raise LookupError("Claim not found")
        if claim.payer.payer_code.upper() != "SHA":
            raise ValueError("Only claims assigned to payer code SHA can use this exchange")
        integration = self.repository.integration(payload.integration_id)
        if integration is None:
            raise LookupError("Integration not found")
        if integration.provider != "sha":
            raise ValueError("Selected integration is not an SHA integration")
        if integration.status == IntegrationStatus.DISCONNECTED:
            raise ValueError("Selected SHA integration is disconnected")
        if not integration.settings:
            raise ValueError("Selected SHA integration has no connector settings")

        organization = self.repository.organization()
        requested_at = datetime.now(UTC)
        bundle = SHABundleBuilder(integration.settings).build(
            claim,
            organization,
            payload,
            requested_at=requested_at,
        )
        bundle_hash = canonical_json_sha256(bundle)
        request_id = correlation_id or str(uuid4())
        exchange = SHAExchange(
            organization_id=self.organization_id,
            claim_id=claim.id,
            integration_id=integration.id,
            initiated_by=actor_id,
            idempotency_key=payload.idempotency_key,
            correlation_id=request_id,
            reason=payload.reason.strip(),
            ig_version=IG_VERSION,
            bundle_identifier=payload.idempotency_key,
            bundle_sha256=bundle_hash,
            status="prepared",
            requested_at=requested_at,
        )
        self.db.add(exchange)
        self.db.flush()
        self._record_event(
            exchange,
            actor_id=actor_id,
            status="prepared",
            correlation_id=request_id,
            reason=payload.reason,
        )
        self.db.commit()
        self.db.refresh(exchange)

        connector = self._connector(integration.id)
        try:
            result = await connector.submit_claim_bundle(
                bundle,
                correlation_id=request_id,
            )
        except SHAConnectorError as exc:
            self._record_failure(
                exchange,
                exc,
                actor_id=actor_id,
                correlation_id=request_id,
                reason=payload.reason,
                submission_failed=True,
            )
            raise

        try:
            self._apply_response(
                exchange,
                result,
                actor_id=actor_id,
                correlation_id=request_id,
                reason=payload.reason,
                submitted=True,
            )
        except SHAConnectorError as exc:
            self._record_failure(
                exchange,
                exc,
                actor_id=actor_id,
                correlation_id=request_id,
                reason=payload.reason,
                submission_failed=True,
            )
            raise
        return exchange

    async def refresh(
        self,
        exchange_id: int,
        *,
        actor_id: int,
        correlation_id: str | None,
        reason: str,
    ) -> SHAExchange:
        exchange = self.get(exchange_id)
        if not exchange.external_reference:
            raise ValueError("SHA exchange has no external ClaimResponse reference")
        request_id = correlation_id or str(uuid4())
        connector = self._connector(exchange.integration_id)
        try:
            result = await connector.get_claim_response(
                exchange.external_reference,
                correlation_id=request_id,
            )
        except SHAConnectorError as exc:
            self._record_failure(
                exchange,
                exc,
                actor_id=actor_id,
                correlation_id=request_id,
                reason=reason,
                submission_failed=False,
            )
            raise

        try:
            self._apply_response(
                exchange,
                result,
                actor_id=actor_id,
                correlation_id=request_id,
                reason=reason,
                submitted=False,
            )
        except SHAConnectorError as exc:
            self._record_failure(
                exchange,
                exc,
                actor_id=actor_id,
                correlation_id=request_id,
                reason=reason,
                submission_failed=False,
            )
            raise
        return exchange

    def get(self, exchange_id: int) -> SHAExchange:
        exchange = self.repository.get(exchange_id)
        if exchange is None:
            raise LookupError("SHA exchange not found")
        return exchange

    def for_claim(self, claim_id: int) -> list[SHAExchange]:
        if self.repository.claim(claim_id) is None:
            raise LookupError("Claim not found")
        return self.repository.for_claim(claim_id)

    def _connector(self, integration_id: int) -> EClaimsConnector:
        connector = IntegrationManager(self.db).connector(
            integration_id,
            self.organization_id,
        )
        if not isinstance(connector, EClaimsConnector):
            raise ValueError("Configured integration does not support eClaims exchange")
        return connector

    def _apply_response(
        self,
        exchange: SHAExchange,
        result: EClaimsTransportResponse,
        *,
        actor_id: int,
        correlation_id: str,
        reason: str,
        submitted: bool,
    ) -> None:
        summary = claim_response_summary(result.resource)
        before = self._state(exchange)
        now = datetime.now(UTC)
        external_reference = (
            summary["claim_response_id"]
            or result.external_reference
            or exchange.external_reference
        )
        if not external_reference:
            raise SHAConnectorError(
                "SHA accepted the request without a retrievable response reference",
                http_status=result.http_status,
                response_sha256=result.response_sha256,
            )
        exchange.external_reference = external_reference
        exchange.claim_response_id = summary["claim_response_id"]
        exchange.outcome = summary["outcome"]
        exchange.workflow_state = summary["workflow_state"]
        exchange.approved_amount = (
            Decimal(str(summary["approved_amount"]))
            if summary["approved_amount"] is not None
            else None
        )
        exchange.currency = summary["currency"]
        exchange.response_sha256 = result.response_sha256
        exchange.last_http_status = result.http_status
        exchange.response_summary = summary
        exchange.error_code = None
        exchange.error_summary = None
        exchange.status = summary["workflow_state"] or summary["outcome"] or "submitted"
        exchange.last_checked_at = now
        if submitted:
            exchange.submitted_at = now
        self._record_event(
            exchange,
            actor_id=actor_id,
            status=exchange.status,
            correlation_id=correlation_id,
            reason=reason,
            http_status=result.http_status,
            response_sha256=result.response_sha256,
            outcome=exchange.outcome,
            workflow_state=exchange.workflow_state,
        )
        AuditService(self.db).log(
            organization_id=self.organization_id,
            user_id=actor_id,
            action=(
                AuditAction.SHA_CLAIM_SUBMITTED
                if submitted
                else AuditAction.SHA_CLAIM_RESPONSE_RECEIVED
            ),
            entity="sha_eclaim_exchange",
            entity_id=exchange.id,
            correlation_id=correlation_id,
            reason=reason.strip(),
            before_state=before,
            after_state=self._state(exchange),
            metadata={
                "claim_id": exchange.claim_id,
                "integration_id": exchange.integration_id,
                "bundle_sha256": exchange.bundle_sha256,
                "response_sha256": exchange.response_sha256,
                "ig_version": exchange.ig_version,
            },
        )
        EventPublisher(self.db).publish(
            (
                EventType.CLAIM_SUBMITTED
                if submitted
                else EventType.CLAIM_ADJUDICATION_RECEIVED
            ),
            {
                "organization_id": self.organization_id,
                "claim_id": exchange.claim_id,
                "exchange_id": exchange.id,
                "integration_id": exchange.integration_id,
                "external_reference": exchange.external_reference,
                "status": exchange.status,
                "outcome": exchange.outcome,
                "workflow_state": exchange.workflow_state,
                "actor_id": actor_id,
                "correlation_id": correlation_id,
            },
            self.organization_id,
        )
        self.db.commit()
        self.db.refresh(exchange)

    def _record_failure(
        self,
        exchange: SHAExchange,
        error: SHAConnectorError,
        *,
        actor_id: int,
        correlation_id: str,
        reason: str,
        submission_failed: bool,
    ) -> None:
        before = self._state(exchange)
        if submission_failed:
            exchange.status = "failed"
        exchange.error_code = type(error).__name__
        exchange.error_summary = str(error)[:1000]
        exchange.last_http_status = error.http_status
        exchange.response_sha256 = error.response_sha256
        exchange.last_checked_at = datetime.now(UTC)
        self._record_event(
            exchange,
            actor_id=actor_id,
            status="failed" if submission_failed else "status_check_failed",
            correlation_id=correlation_id,
            reason=reason,
            http_status=error.http_status,
            response_sha256=error.response_sha256,
            error_code=type(error).__name__,
            error_summary=str(error)[:1000],
        )
        AuditService(self.db).log(
            organization_id=self.organization_id,
            user_id=actor_id,
            action=(
                AuditAction.SHA_CLAIM_SUBMISSION_FAILED
                if submission_failed
                else AuditAction.SHA_CLAIM_STATUS_CHECK_FAILED
            ),
            entity="sha_eclaim_exchange",
            entity_id=exchange.id,
            correlation_id=correlation_id,
            reason=reason.strip(),
            before_state=before,
            after_state=self._state(exchange),
            metadata={
                "claim_id": exchange.claim_id,
                "integration_id": exchange.integration_id,
                "http_status": error.http_status,
                "response_sha256": error.response_sha256,
            },
        )
        EventPublisher(self.db).publish(
            (
                EventType.CLAIM_SUBMISSION_FAILED
                if submission_failed
                else EventType.CLAIM_ADJUDICATION_CHECK_FAILED
            ),
            {
                "organization_id": self.organization_id,
                "claim_id": exchange.claim_id,
                "exchange_id": exchange.id,
                "integration_id": exchange.integration_id,
                "status": exchange.status,
                "actor_id": actor_id,
                "correlation_id": correlation_id,
            },
            self.organization_id,
        )
        self.db.commit()
        self.db.refresh(exchange)

    def _record_event(
        self,
        exchange: SHAExchange,
        *,
        actor_id: int,
        status: str,
        correlation_id: str,
        reason: str,
        http_status: int | None = None,
        response_sha256: str | None = None,
        outcome: str | None = None,
        workflow_state: str | None = None,
        error_code: str | None = None,
        error_summary: str | None = None,
    ) -> None:
        self.db.add(
            SHAExchangeEvent(
                exchange_id=exchange.id,
                organization_id=self.organization_id,
                actor_id=actor_id,
                status=status,
                http_status=http_status,
                response_sha256=response_sha256,
                outcome=outcome,
                workflow_state=workflow_state,
                error_code=error_code,
                error_summary=error_summary,
                correlation_id=correlation_id,
                reason=reason.strip(),
                created_at=datetime.now(UTC),
            )
        )

    @staticmethod
    def _state(exchange: SHAExchange) -> dict:
        return {
            "status": exchange.status,
            "external_reference": exchange.external_reference,
            "claim_response_id": exchange.claim_response_id,
            "outcome": exchange.outcome,
            "workflow_state": exchange.workflow_state,
            "approved_amount": (
                str(exchange.approved_amount)
                if exchange.approved_amount is not None
                else None
            ),
            "currency": exchange.currency,
            "error_code": exchange.error_code,
        }
