import asyncio
import logging

from app.events.handlers import register_all as register_event_handlers
from app.tasks.ai_analysis import analyze_claim_task as analyze_claim_task
from app.tasks.generate_appeal import generate_appeal_task as generate_appeal_task
from app.workers.celery_app import celery

logger = logging.getLogger(__name__)

# The worker process never imports app.main, so event handlers must be
# registered here too — events published inside tasks (e.g. CLAIM_IMPORTED
# from ImportPipeline, PAYMENT_RECEIVED from the recovery workspace) need
# their subscribers registered in whichever process actually publishes them.
register_event_handlers()


@celery.task(name="tasks.process_import")
def process_import(job_id: int):
    """Process a queued import job by running the full import pipeline."""
    from app.db.database import get_db
    from app.imports.import_job_service import ImportJobService
    from app.models.import_job import ImportJob
    from app.processing.pipeline import ImportPipeline

    db = next(get_db())
    try:
        # Trusted internal lookup (job_id is never client-supplied here — it
        # was minted by our own upload endpoint) just to discover which
        # organization owns this job before switching to the org-scoped
        # service/repository for every subsequent read/write.
        job = db.query(ImportJob).filter(ImportJob.id == job_id).first()
        if job is None or not job.filename:
            return

        job_service = ImportJobService(db, job.organization_id)
        job_service.start(job_id)

        def _update_progress(snapshot: dict) -> None:
            job_service.update_progress(job_id, **snapshot)

        try:
            result = ImportPipeline(db, job.organization_id).run(
                job.filename, on_progress=_update_progress
            )
        except Exception as exc:  # noqa: BLE001 - persist failure reason on the job
            db.rollback()
            job_service.fail(job_id, str(exc))
            return

        job_service.complete(job_id, result)
    finally:
        db.close()



@celery.task(name="tasks.sync_integration")
def sync_integration(
    integration_id: int,
    organization_id: int,
    correlation_id: str | None = None,
):
    """Run a full sync for one integration (called by scheduler)."""
    from app.integrations.jobs import run_sync_job
    return run_sync_job(integration_id, organization_id, correlation_id)


@celery.task(name="tasks.schedule_sftp_syncs")
def schedule_sftp_syncs():
    """Queue every active or pending SFTP claim feed."""
    from app.db.database import get_db
    from app.models.integration import Integration, IntegrationStatus

    db = next(get_db())
    try:
        rows = db.query(Integration.id, Integration.organization_id).filter(
            Integration.provider == "sftp",
            Integration.status.in_([IntegrationStatus.ACTIVE, IntegrationStatus.PENDING]),
        ).all()
        for integration_id, organization_id in rows:
            sync_integration.delay(integration_id, organization_id)
        return {"queued": len(rows)}
    finally:
        db.close()


@celery.task(
    name="tasks.submit_payer_appeal",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=3,
)
def submit_payer_appeal(
    self,
    appeal_id: int,
    organization_id: int,
    connector: str,
    integration_id: int,
):
    """Submit one approved appeal through the configured payer connector."""
    from app.db.database import get_db
    from app.payer_connectivity.service import PayerSubmissionService

    db = next(get_db())
    try:
        return asyncio.run(PayerSubmissionService(db, organization_id).submit(
            appeal_id=appeal_id,
            connector=connector,
            integration_id=integration_id,
        )).id
    finally:
        db.close()


@celery.task(name="tasks.check_pending_payer_submissions")
def check_pending_payer_submissions():
    """Poll every externally active appeal and normalize payer statuses."""
    from app.db.database import get_db
    from app.models.appeal_submission import (
        AppealSubmission,
        AppealSubmissionEvent,
        AppealSubmissionStatus,
    )
    from app.payer_connectivity.service import PayerSubmissionService

    db = next(get_db())
    try:
        trackable = [
            AppealSubmissionStatus.SUBMITTED,
            AppealSubmissionStatus.ACKNOWLEDGED,
            AppealSubmissionStatus.IN_REVIEW,
            AppealSubmissionStatus.UNDER_REVIEW,
            AppealSubmissionStatus.ADDITIONAL_INFO_REQUIRED,
            AppealSubmissionStatus.APPROVED,
            AppealSubmissionStatus.ACCEPTED,
        ]
        rows = db.query(AppealSubmission.id, AppealSubmission.organization_id).filter(
            AppealSubmission.status.in_(trackable)
        ).all()
        for submission_id, organization_id in rows:
            try:
                asyncio.run(PayerSubmissionService(db, organization_id).refresh(submission_id))
            except Exception:
                logger.exception("Could not refresh payer submission %s", submission_id)
                db.rollback()
    finally:
        db.close()


@celery.task(name="tasks.generate_monthly_recovery_invoices")
def generate_monthly_recovery_invoices():
    """Generate and email itemized invoices for last month's verified recoveries."""
    from datetime import date, timedelta

    from app.db.database import get_db
    from app.models.organization import Organization
    from app.invoices.service import InvoiceService

    first_of_this_month = date.today().replace(day=1)
    last_month = first_of_this_month - timedelta(days=1)
    db = next(get_db())
    try:
        organization_ids = [row[0] for row in db.query(Organization.id).all()]
        for organization_id in organization_ids:
            try:
                service = InvoiceService(db, organization_id)
                invoice = service.generate_monthly(last_month.year, last_month.month)
                if invoice.status.value == "draft":
                    service.mark_sent(invoice.id)
            except ValueError:
                db.rollback()
            except Exception:
                logger.exception(
                    "Could not generate monthly recovery invoice for organization %s",
                    organization_id,
                )
                db.rollback()
    finally:
        db.close()


@celery.task(name="tasks.check_payer_follow_ups")
def check_payer_follow_ups():
    """Publish follow-up work signals for payer submissions past their deadline."""
    from datetime import datetime, timedelta

    from app.db.database import get_db
    from app.events.event_types import EventType
    from app.events.publisher import EventPublisher
    from app.models.appeal_submission import (
        AppealSubmission,
        AppealSubmissionEvent,
        AppealSubmissionStatus,
    )

    db = next(get_db())
    try:
        rows = db.query(AppealSubmission).filter(
            AppealSubmission.next_follow_up_at.isnot(None),
            AppealSubmission.next_follow_up_at <= datetime.utcnow(),
            AppealSubmission.status.in_([
                AppealSubmissionStatus.SUBMITTED,
                AppealSubmissionStatus.ACKNOWLEDGED,
                AppealSubmissionStatus.UNDER_REVIEW,
            ]),
        ).all()
        for row in rows:
            db.add(AppealSubmissionEvent(
                organization_id=row.organization_id,
                submission_id=row.id,
                status=row.status,
                message="Payer follow-up due; analyst notification queued",
                payload={"external_tracking_id": row.external_tracking_id},
            ))
            EventPublisher().publish(EventType.APPEAL_FOLLOW_UP_DUE, {
                "organization_id": row.organization_id,
                "submission_id": row.id,
                "appeal_id": row.appeal_id,
                "external_tracking_id": row.external_tracking_id,
            })
            row.next_follow_up_at = datetime.utcnow() + timedelta(days=7)
        db.commit()
    finally:
        db.close()


@celery.task(
    name="tasks.deliver_webhook",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
    max_retries=3,
)
def deliver_webhook(subscription_id: int, event_type: str, payload: dict):
    """
    POST one event to one registered webhook subscription's target_url,
    signing the body with the subscription's secret (HMAC-SHA256, sent as
    the `X-Atlas-Signature` header) so the receiver can verify authenticity.
    Logs the outcome to WebhookDeliveryLog either way — no dead-letter
    queue/replay mechanism yet (deliberately deferred, see local dev notes).
    """
    import hashlib
    import hmac
    import json

    import httpx

    from app.db.database import get_db
    from app.models.webhook import WebhookDeliveryLog, WebhookSubscription

    db = next(get_db())
    try:
        subscription = db.query(WebhookSubscription).filter(WebhookSubscription.id == subscription_id).first()
        if subscription is None or not subscription.is_active:
            return

        body = json.dumps({"event": event_type, "data": payload}, default=str)
        signature = hmac.new(subscription.secret.encode(), body.encode(), hashlib.sha256).hexdigest()

        success = False
        status_code = None
        error = None
        try:
            response = httpx.post(
                subscription.target_url,
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Atlas-Signature": signature,
                    "X-Atlas-Event": event_type,
                },
                timeout=5.0,
            )
            status_code = response.status_code
            success = 200 <= response.status_code < 300
        except httpx.HTTPError as exc:
            error = str(exc)

        db.add(WebhookDeliveryLog(
            subscription_id=subscription.id,
            event_type=event_type,
            success=success,
            status_code=status_code,
            error=error,
        ))
        db.commit()
    finally:
        db.close()


@celery.task(name="tasks.check_workflow_escalations")
def check_workflow_escalations():
    """
    Sweep every organization for overdue Recovery Workflow Engine stages
    that need escalation (see app/workflows/escalation.py). Not currently
    wired to a Celery Beat schedule — no periodic scheduler is configured
    in this deployment yet, so invoke manually or via
    POST /workflows/escalate-sweep, or add a beat schedule entry pointing
    at this task name once one exists.
    """
    from app.db.database import get_db
    from app.models.organization import Organization
    from app.workflows.escalation import run_escalation_sweep

    db = next(get_db())
    try:
        org_ids = [row[0] for row in db.query(Organization.id).all()]
        for org_id in org_ids:
            run_escalation_sweep(db, org_id)
    finally:
        db.close()


@celery.task(
    name="tasks.resume_workflow_execution",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def resume_workflow_execution(self, execution_id: int):
    """
    Fires once a Sprint 5 Workflow Engine WAIT step's configured delay has
    elapsed — dispatched via `apply_async(countdown=...)` from
    WorkflowEngine._schedule_resume (see app/workflow_engine/engine.py).
    Resumes the execution from the step after the WAIT step, exactly the
    same way a HUMAN_APPROVAL resume does.
    """
    from app.db.database import get_db
    from app.models.workflow_execution import WorkflowExecution
    from app.workflow_engine.engine import WorkflowEngine

    db = next(get_db())
    try:
        execution = db.query(WorkflowExecution).filter(WorkflowExecution.id == execution_id).first()
        if execution is None:
            return
        asyncio.run(WorkflowEngine(db, execution.organization_id).resume(execution_id))
    finally:
        db.close()


@celery.task(
    name="tasks.process_workflow_event",
    bind=True,
    max_retries=3,
)
def process_workflow_event(self, workflow_event_id: int):
    """Process one durable workflow event with exponential retry and DLQ."""
    from app.db.database import get_db
    from app.workflows.engine import WorkflowEventEngine
    from app.workflows.models import WorkflowEvent

    db = next(get_db())
    try:
        event = db.query(WorkflowEvent).filter(WorkflowEvent.id == workflow_event_id).first()
        if event is None:
            return
        engine = WorkflowEventEngine(db, event.organization_id)
        try:
            return asyncio.run(engine.process(workflow_event_id))
        except Exception as exc:
            if self.request.retries >= self.max_retries:
                engine.dead_letter(workflow_event_id, str(exc))
                return
            raise self.retry(
                exc=exc,
                countdown=min(300, 2 ** (self.request.retries + 1)),
            )
    finally:
        db.close()


@celery.task(name="tasks.requeue_pending_workflow_events")
def requeue_pending_workflow_events():
    """Recover events persisted while the broker or worker was unavailable."""
    from app.db.database import get_db
    from app.workflows.models import WorkflowEvent, WorkflowEventStatus

    db = next(get_db())
    try:
        event_ids = [
            row[0]
            for row in db.query(WorkflowEvent.id)
            .filter(WorkflowEvent.status == WorkflowEventStatus.PENDING.value)
            .order_by(WorkflowEvent.received_at)
            .limit(500)
            .all()
        ]
        for event_id in event_ids:
            process_workflow_event.delay(event_id)
        return len(event_ids)
    finally:
        db.close()


@celery.task(name="tasks.reconcile_recovery_lifecycles")
def reconcile_recovery_lifecycles():
    """Open/synchronize a recovery lifecycle account for every tracked claim.

    Every claim with a recovery case is a candidate lifecycle account. This
    sweep opens the account if it does not exist yet and replays any verified
    recoveries into it, across every tenant. It is safe to rerun: opening an
    already-open account and synchronizing already-applied recoveries are
    both no-ops (RecoveryLifecycleService keys both off existing records).

    The actor is "system" rather than "user" since no human triggered this
    run; call RecoveryLifecycleService directly instead of
    RevenueRecoveryService.open_account (which always attributes to "user").
    """
    from app.db.database import get_db
    from app.models.claim import Claim
    from app.models.recovery_case import RecoveryCase
    from app.organizations.service import OrganizationService
    from app.recovery.lifecycle import RecoveryLifecycleService

    db = next(get_db())
    try:
        claims = (
            db.query(Claim.id, Claim.organization_id)
            .join(RecoveryCase, RecoveryCase.claim_id == Claim.id)
            .distinct()
            .all()
        )
        reconciled_organizations: set[int] = set()
        for claim_id, organization_id in claims:
            try:
                currency = OrganizationService(db, organization_id).get().currency
                lifecycle = RecoveryLifecycleService(db, organization_id, currency)
                account = lifecycle.open_account(
                    claim_id,
                    actor_id=None,
                    actor_type="system",
                    reason="Automated recovery lifecycle reconciliation",
                    correlation_id=None,
                )
                lifecycle.synchronize_verified_recoveries(
                    account,
                    actor_id=None,
                    actor_type="system",
                    correlation_id=None,
                )
                db.commit()
            except ValueError:
                db.rollback()
                continue
            except Exception:
                logger.exception(
                    "Could not reconcile recovery lifecycle for claim %s", claim_id
                )
                db.rollback()
                continue
            reconciled_organizations.add(organization_id)
        return {"processed": len(claims), "organizations": len(reconciled_organizations)}
    finally:
        db.close()
