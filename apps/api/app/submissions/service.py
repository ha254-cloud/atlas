from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

import app.integrations.mock  # noqa: F401 - registers built-in submission connectors
from app.appeals.service import AppealService
from app.claims.timeline import ClaimTimeline
from app.documents.storage import read_file
from app.events.event_types import EventType
from app.events.publisher import EventPublisher
from app.integrations.base import SubmissionAttachment, SubmissionPayload
from app.integrations.manager import IntegrationManager
from app.integrations.registry import submission_registry
from app.models.appeal import Appeal, AppealStatus
from app.models.claim import Claim
from app.models.claim_event import ClaimEventType
from app.models.claim_workflow import ClaimWorkflowState
from app.models.integration import Integration, IntegrationStatus
from app.models.recovery_case import RecoveryCase, RecoveryStatus
from app.models.submission import Submission, SubmissionEvent, SubmissionStatus
from app.payments.models import PaymentSource, PaymentStatus
from app.payments.schemas import PaymentIngest
from app.payments.service import PaymentService
from app.submissions.repository import SubmissionRepository
from app.workflows.service import WorkflowService

_TRACKABLE = {
    SubmissionStatus.SUBMITTED,
    SubmissionStatus.ACKNOWLEDGED,
    SubmissionStatus.IN_REVIEW,
    SubmissionStatus.UNDER_REVIEW,
    SubmissionStatus.ADDITIONAL_INFO_REQUIRED,
    SubmissionStatus.APPROVED,
    SubmissionStatus.ACCEPTED,
}
_TERMINAL = {
    SubmissionStatus.APPROVED,
    SubmissionStatus.DENIED,
    SubmissionStatus.PAID,
    SubmissionStatus.FAILED,
    SubmissionStatus.ACCEPTED,
    SubmissionStatus.REJECTED,
}


class SubmissionService:
    def __init__(self, db: Session, organization_id: int) -> None:
        self.db = db
        self.organization_id = organization_id
        self.repository = SubmissionRepository(db, organization_id)
        self.publisher = EventPublisher()

    async def submit(
        self,
        appeal_id: int,
        connector: str | None = None,
        integration_id: int | None = None,
        submitted_by: int | None = None,
        connector_options: dict | None = None,
    ) -> Submission:
        appeal = self._appeal(appeal_id)
        existing = self._for_appeal(appeal_id)
        if existing is not None and existing.status != SubmissionStatus.FAILED:
            return existing
        if appeal.status != AppealStatus.APPROVED:
            raise ValueError("Submission requires a human-approved appeal")
        blockers = AppealService(self.db, self.organization_id).check_submission_readiness(appeal_id)
        if blockers:
            raise ValueError("Appeal is not ready for submission: " + " ".join(blockers))

        claim = self._claim(appeal.claim_id)
        connector_name, integration, config = self._resolve_connector(
            connector,
            integration_id,
            payer=claim.payer,
        )
        config.update(connector_options or {})
        transport = submission_registry.get(connector_name, **config)

        submission = existing or Submission(
            organization_id=self.organization_id,
            claim_id=claim.id,
            appeal_id=appeal.id,
            connector=connector_name,
        )
        submission.claim_id = claim.id
        submission.integration_id = integration.id if integration else None
        submission.connector = connector_name
        submission.status = SubmissionStatus.SUBMITTING
        submission.failure_reason = None
        is_new = existing is None
        if existing is None:
            self.db.add(submission)
            self.db.flush()
        self._record(submission, SubmissionStatus.SUBMITTING, "Submitting appeal")

        attachment_files = []
        if appeal.pdf_document is not None:
            if (
                appeal.pdf_document.organization_id != self.organization_id
                or appeal.pdf_document.claim_id != claim.id
            ):
                raise ValueError("Approved appeal PDF does not match the submission tenant and claim")
            attachment_files.append(
                SubmissionAttachment(
                    filename=appeal.pdf_document.filename,
                    content=read_file(appeal.pdf_document.storage_path),
                    content_type=appeal.pdf_document.content_type,
                )
            )

        payload = SubmissionPayload(
            appeal_id=appeal.id,
            claim_id=claim.id,
            claim_number=claim.claim_number,
            payer_code=claim.payer.payer_code,
            appeal_text=appeal.appeal_text,
            attachments=list(appeal.attachments or []),
            attachment_files=attachment_files,
        )
        try:
            result = await transport.submit_appeal(payload)
            now = datetime.utcnow()
            submission.external_reference = result.external_reference
            submission.status = result.status
            submission.submitted_at = now
            submission.last_checked_at = now
            submission.next_follow_up_at = now + timedelta(days=30)
            submission.response_payload = result.payload
            submission.failure_reason = None
            self._apply_status_timestamps(submission, result.status, now)
            self._record(submission, result.status, result.message, result.payload)
            self.db.commit()

            AppealService(self.db, self.organization_id).submit_appeal(
                appeal.id,
                submitted_by=submitted_by,
                confirmation_number=result.external_reference,
            )
            if is_new:
                self._publish(EventType.SUBMISSION_CREATED, submission)
            self._publish(EventType.SUBMISSION_SUBMITTED, submission)
            self._publish(EventType.APPEAL_SUBMISSION_UPDATED, submission)
            self.db.refresh(submission)
            return submission
        except Exception as exc:
            submission.status = SubmissionStatus.FAILED
            submission.retry_count += 1
            submission.failure_reason = str(exc)
            submission.completed_at = datetime.utcnow()
            self._record(submission, SubmissionStatus.FAILED, str(exc))
            self.db.commit()
            if is_new:
                self._publish(EventType.SUBMISSION_CREATED, submission)
            self._publish(EventType.SUBMISSION_FAILED, submission)
            raise

    async def status(self, submission_id: int) -> Submission:
        submission = self.get(submission_id)
        if submission.status not in _TRACKABLE:
            return submission
        if not submission.external_reference:
            raise ValueError(f"Submission {submission_id} has no external reference")

        _, _, config = self._resolve_connector(
            submission.connector,
            submission.integration_id,
        )
        transport = submission_registry.get(submission.connector, **config)
        try:
            result = await transport.check_status(submission.external_reference)
        except Exception as exc:
            submission.retry_count += 1
            submission.failure_reason = str(exc)
            self.db.commit()
            raise

        previous = submission.status
        now = datetime.utcnow()
        submission.status = result.status
        submission.last_checked_at = now
        submission.response_payload = dict(result.payload)
        if result.paid_amount is not None:
            submission.response_payload["paid_amount"] = float(result.paid_amount)
        submission.failure_reason = None
        self._apply_status_timestamps(submission, result.status, now)
        if previous != result.status:
            self._record(submission, result.status, result.message, result.payload)
            self._record_claim_status(submission, result.status, result.message)
        if result.status == SubmissionStatus.PAID and previous != result.status:
            self._apply_payment(submission, result.paid_amount)
        self.db.commit()
        self._publish_status_event(submission, previous)
        self.db.refresh(submission)
        return submission

    async def refresh(self, submission_id: int) -> Submission:
        return await self.status(submission_id)

    async def cancel(self, submission_id: int) -> Submission:
        submission = self.get(submission_id)
        if not submission.external_reference:
            raise ValueError(f"Submission {submission_id} has no external reference")
        _, _, config = self._resolve_connector(
            submission.connector,
            submission.integration_id,
        )
        result = await submission_registry.get(submission.connector, **config).cancel(
            submission.external_reference
        )
        submission.status = result.status
        submission.completed_at = datetime.utcnow()
        submission.response_payload = result.payload
        self._record(submission, result.status, result.message, result.payload)
        self.db.commit()
        self._publish(EventType.SUBMISSION_FAILED, submission)
        self.db.refresh(submission)
        return submission

    def get(self, submission_id: int) -> Submission:
        submission = self.repository.get(submission_id)
        if submission is None:
            raise ValueError(f"Submission {submission_id} not found")
        return submission

    def list(self, status: SubmissionStatus | None = None) -> list[Submission]:
        return self.repository.list(status)

    def check_all_pending(self) -> int:
        raise RuntimeError("Use check_pending_submissions Celery task for connector polling")

    def _appeal(self, appeal_id: int) -> Appeal:
        appeal = self.db.query(Appeal).filter(
            Appeal.id == appeal_id,
            Appeal.organization_id == self.organization_id,
        ).first()
        if appeal is None:
            raise ValueError(f"Appeal {appeal_id} not found")
        return appeal

    def _claim(self, claim_id: int) -> Claim:
        claim = self.db.query(Claim).filter(
            Claim.id == claim_id,
            Claim.organization_id == self.organization_id,
        ).first()
        if claim is None:
            raise ValueError(f"Claim {claim_id} not found")
        return claim

    def _for_appeal(self, appeal_id: int) -> Submission | None:
        return self.repository.for_appeal(appeal_id)

    def _resolve_connector(
        self,
        connector: str | None,
        integration_id: int | None,
        payer=None,
    ) -> tuple[str, Integration | None, dict]:
        integration = None
        if integration_id is not None:
            integration = IntegrationManager(self.db).get_integration(
                integration_id,
                self.organization_id,
            )
        elif connector is None and payer is not None and payer.connector_name:
            connector = payer.connector_name
            if payer.integration_id is not None:
                integration = IntegrationManager(self.db).get_integration(
                    payer.integration_id,
                    self.organization_id,
                )
        elif connector is None:
            integration = self.db.query(Integration).filter(
                Integration.organization_id == self.organization_id,
                Integration.status == IntegrationStatus.ACTIVE,
            ).all()
            integration = next(
                (
                    item for item in integration
                    if (item.settings or {}).get("submission_enabled", False)
                ),
                None,
            )

        if integration is not None:
            configured = (integration.settings or {}).get("submission_connector")
            expected_connector = str(configured or integration.provider).lower()
            connector_name = (connector or expected_connector).lower()
            if connector and connector.lower() != expected_connector:
                raise ValueError(
                    f"Integration {integration.id} uses submission connector "
                    f"{expected_connector}, not {connector}"
                )
            config = IntegrationManager(self.db)._build_config(integration)
            return connector_name, integration, config

        connector_name = (connector or "mock").lower()
        if connector_name not in {"mock", "sandbox"}:
            raise ValueError("integration_id is required for non-mock connectors")
        return connector_name, None, {"organization_id": self.organization_id}

    def _record(
        self,
        submission: Submission,
        status: SubmissionStatus,
        message: str | None,
        payload: dict | None = None,
    ) -> None:
        self.db.add(SubmissionEvent(
            organization_id=self.organization_id,
            submission_id=submission.id,
            status=status,
            message=message,
            payload=payload,
        ))

    def _record_claim_status(
        self,
        submission: Submission,
        status: SubmissionStatus,
        message: str | None,
    ) -> None:
        ClaimTimeline(self.db).record(
            organization_id=self.organization_id,
            claim_id=submission.claim_id or submission.appeal.claim_id,
            event_type=ClaimEventType.APPEAL_STATUS_UPDATED,
            description=f"Submission status: {status.value}",
            metadata={
                "submission_id": submission.id,
                "external_reference": submission.external_reference,
                "message": message,
            },
        )

    def _apply_payment(
        self,
        submission: Submission,
        paid_amount: Decimal | None,
    ) -> None:
        if paid_amount is None or paid_amount <= 0:
            submission.failure_reason = (
                "Connector reported paid without an amount; financial outcome requires reconciliation"
            )
            return
        appeal = submission.appeal
        claim = self._claim(appeal.claim_id)
        recovery_case = None
        if appeal.recovery_case_id is not None:
            recovery_case = self.db.query(RecoveryCase).filter(
                RecoveryCase.id == appeal.recovery_case_id,
                RecoveryCase.organization_id == self.organization_id,
            ).first()
        if recovery_case is not None:
            recovery_case.recovered_amount = paid_amount
            recovery_case.atlas_fee = paid_amount * Decimal("0.05")
            recovery_case.payment_received_at = datetime.utcnow()
            recovery_case.status = RecoveryStatus.RECOVERED
        result = PaymentService(self.db, self.organization_id).ingest(PaymentIngest(
            claim_id=claim.id,
            submission_id=submission.id,
            payer_name=claim.payer.name,
            payment_reference=(
                f"{submission.connector}:"
                f"{submission.external_reference or submission.id}:paid"
            ),
            payment_date=date.today(),
            expected_amount=claim.billed_amount or Decimal("0"),
            paid_amount=paid_amount,
            adjustment_amount=(claim.billed_amount or Decimal("0")) - paid_amount,
            currency=claim.currency,
            payment_method=submission.connector,
            status=PaymentStatus.PAID,
            source=PaymentSource.API,
            raw_payload=dict(submission.response_payload or {}),
        ))
        recovery = result.payment.recovery
        ClaimTimeline(self.db).record(
            organization_id=self.organization_id,
            claim_id=appeal.claim_id,
            event_type=ClaimEventType.PAYMENT_RECEIVED,
            description=f"Payer payment detected: {paid_amount}",
            metadata={"submission_id": submission.id, "recovered_amount": float(paid_amount)},
        )
        WorkflowService(self.db, self.organization_id).try_transition(
            appeal.claim_id,
            ClaimWorkflowState.RECOVERED,
            reason="Payer payment detected",
        )
        self.publisher.publish(EventType.PAYMENT_RECEIVED, {
            "organization_id": self.organization_id,
            "claim_id": appeal.claim_id,
            "submission_id": submission.id,
            "recovery_case_id": recovery_case.id if recovery_case else None,
            "recovery_id": recovery.id,
            "payment_id": result.payment.id,
            "recovered_amount": float(paid_amount),
        })

    @staticmethod
    def _apply_status_timestamps(
        submission: Submission,
        status: SubmissionStatus,
        now: datetime,
    ) -> None:
        if status == SubmissionStatus.ACKNOWLEDGED and submission.acknowledged_at is None:
            submission.acknowledged_at = now
        if status in _TERMINAL:
            submission.completed_at = now

    def _publish_status_event(
        self,
        submission: Submission,
        previous: SubmissionStatus,
    ) -> None:
        if previous == submission.status:
            return
        event_type = {
            SubmissionStatus.ACKNOWLEDGED: EventType.SUBMISSION_ACKNOWLEDGED,
            SubmissionStatus.PAID: EventType.SUBMISSION_PAID,
            SubmissionStatus.FAILED: EventType.SUBMISSION_FAILED,
        }.get(submission.status)
        if event_type is not None:
            self._publish(event_type, submission)
        self._publish(EventType.APPEAL_SUBMISSION_UPDATED, submission)

    def _publish(self, event_type: EventType, submission: Submission) -> None:
        self.publisher.publish(event_type, {
            "organization_id": self.organization_id,
            "submission_id": submission.id,
            "claim_id": submission.claim_id,
            "appeal_id": submission.appeal_id,
            "status": submission.status.value,
            "external_reference": submission.external_reference,
        })
