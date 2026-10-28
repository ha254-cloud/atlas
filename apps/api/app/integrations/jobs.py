"""
Background job definitions for integration sync.

These are called by the Celery worker (apps/api/app/workers/).
Each job fetches the integration row, runs the manager, then
hands the result to the SyncOrchestrator for persistence.
"""

from sqlalchemy.orm import Session

from app.db.database import get_db
from app.events.event_types import EventType
from app.events.publisher import EventPublisher
from app.integrations.exceptions import SyncError
from app.integrations.history import IntegrationSyncHistoryService
from app.integrations.manager import IntegrationManager
from app.integrations.sync import SyncOrchestrator
from app.models.integration import Integration


def run_sync_job(
    integration_id: int,
    organization_id: int,
    correlation_id: str | None = None,
    *,
    initiated_by: int | None = None,
    trigger: str = "scheduled",
) -> dict:
    """
    Entry point called by Celery to sync a single integration.
    Opens its own DB session so the worker is independent of the API process.
    """
    db: Session = next(get_db())
    publisher = EventPublisher()
    history = IntegrationSyncHistoryService(db, organization_id)
    run = history.start(
        integration_id,
        trigger=trigger,
        initiated_by=initiated_by,
        correlation_id=correlation_id,
    )

    try:
        import asyncio

        manager = IntegrationManager(db)
        result = asyncio.run(manager.sync(integration_id, organization_id))

        orchestrator = SyncOrchestrator(db, organization_id, integration_id=integration_id)
        summary = orchestrator.process(result)
        history.complete(run, summary, result.rejection_details)

        row = manager.get_integration(integration_id, organization_id)
        if summary["errors"] and not summary["claims_imported"]:
            from app.models.integration import IntegrationStatus

            row.status = IntegrationStatus.ERROR
            row.last_error = "; ".join(summary["errors"][:3])
            db.commit()
        else:
            file_ids = {claim.external_id for claim in result.claims if claim.external_id}
            if file_ids:
                settings = dict(row.settings or {})
                processed = list(
                    dict.fromkeys(
                        [*(settings.get("processed_files") or []), *sorted(file_ids)]
                    )
                )
                settings["processed_files"] = processed[-1000:]
                row.settings = settings
                db.commit()

        summary["correlation_id"] = correlation_id
        publisher.publish(EventType.CLAIMS_SYNCED, summary)

        return summary

    except SyncError as exc:
        history.fail(run, exc)
        publisher.publish(
            EventType.SYNC_FAILED,
            {
                "integration_id": integration_id,
                "organization_id": organization_id,
                "error": str(exc),
                "correlation_id": correlation_id,
            },
        )
        raise

    finally:
        db.close()


def schedule_all_syncs(db: Session) -> list[int]:
    """
    Enqueue sync jobs for every active integration.
    Called by a periodic scheduler (cron / Celery Beat).
    """
    from app.workers.tasks import sync_integration

    active = (
        db.query(Integration)
        .filter(Integration.status.in_(["active", "pending"]))
        .all()
    )

    job_ids = []
    for integration in active:
        sync_integration.delay(integration.id, integration.organization_id)
        job_ids.append(integration.id)

    return job_ids
