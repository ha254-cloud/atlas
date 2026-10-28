from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from app.integrations.mapping import IntegrationMappingService
from app.models.integration import (
    Integration,
    IntegrationSyncError,
    IntegrationSyncRun,
)


class IntegrationSyncHistoryService:
    def __init__(self, db: Session, organization_id: int):
        self.db = db
        self.organization_id = organization_id

    def start(
        self,
        integration_id: int,
        *,
        trigger: str,
        initiated_by: int | None,
        correlation_id: str | None,
    ) -> IntegrationSyncRun:
        integration = self._integration(integration_id)
        profile = IntegrationMappingService(self.db, self.organization_id).latest_profile(
            integration.id
        )
        run = IntegrationSyncRun(
            organization_id=self.organization_id,
            integration_id=integration.id,
            mapping_profile_id=profile.id if profile else None,
            trigger=trigger,
            status="running",
            initiated_by=initiated_by,
            correlation_id=correlation_id or str(uuid4()),
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return run

    def complete(
        self,
        run: IntegrationSyncRun,
        summary: dict,
        rejection_details: list[dict],
    ) -> IntegrationSyncRun:
        imported = int(summary.get("claims_imported", 0))
        rejected = len(rejection_details)
        run.records_received = imported + rejected
        run.records_imported = imported
        run.records_rejected = rejected
        run.status = "partial" if rejected else "success"
        run.error_summary = "; ".join(summary.get("errors", [])[:3]) or None
        run.completed_at = datetime.now(UTC)
        self.db.add_all(
            IntegrationSyncError(
                sync_run_id=run.id,
                row_number=detail.get("row_number"),
                source_field=detail.get("source_field"),
                error_code=detail.get("error_code", "sync_error"),
                message=str(detail.get("message", "Record rejected"))[:500],
            )
            for detail in rejection_details
        )
        self.db.commit()
        self.db.refresh(run)
        return run

    def fail(self, run: IntegrationSyncRun, error: Exception) -> IntegrationSyncRun:
        run.status = "failed"
        run.error_summary = str(error)[:2000]
        run.completed_at = datetime.now(UTC)
        self.db.commit()
        self.db.refresh(run)
        return run

    def list_runs(self, integration_id: int, limit: int = 50) -> list[IntegrationSyncRun]:
        self._integration(integration_id)
        return (
            self.db.query(IntegrationSyncRun)
            .filter(
                IntegrationSyncRun.integration_id == integration_id,
                IntegrationSyncRun.organization_id == self.organization_id,
            )
            .order_by(IntegrationSyncRun.started_at.desc(), IntegrationSyncRun.id.desc())
            .limit(limit)
            .all()
        )

    def list_errors(self, integration_id: int, run_id: int) -> list[IntegrationSyncError]:
        run = self.get_run(integration_id, run_id)
        return (
            self.db.query(IntegrationSyncError)
            .filter(IntegrationSyncError.sync_run_id == run.id)
            .order_by(IntegrationSyncError.id)
            .all()
        )

    def get_run(self, integration_id: int, run_id: int) -> IntegrationSyncRun:
        self._integration(integration_id)
        run = (
            self.db.query(IntegrationSyncRun)
            .filter(
                IntegrationSyncRun.id == run_id,
                IntegrationSyncRun.integration_id == integration_id,
                IntegrationSyncRun.organization_id == self.organization_id,
            )
            .first()
        )
        if run is None:
            raise ValueError("Sync run not found")
        return run

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
