import logging

logger = logging.getLogger(__name__)


class AppealGeneratedHandler:
    """Apply audit and workflow side effects after appeal persistence commits."""

    def __call__(
        self,
        event_type: str,
        payload: dict,
        organization_id: int | None,
    ) -> None:
        claim_id = payload.get("claim_id")
        appeal_id = payload.get("appeal_id")
        requested_by = payload.get("requested_by")
        if None in (claim_id, appeal_id, requested_by, organization_id):
            return

        from app.audit.actions import AuditAction
        from app.audit.service import AuditService
        from app.db.database import get_db
        from app.models.claim_workflow import ClaimWorkflowState
        from app.workflows.service import WorkflowService

        db = next(get_db())
        try:
            AuditService(db).log(
                organization_id=organization_id,
                user_id=requested_by,
                action=AuditAction.APPEAL_GENERATED,
                entity="appeal",
                entity_id=appeal_id,
                metadata={
                    "claim_id": claim_id,
                    "version": payload.get("version"),
                },
            )
            WorkflowService(db, organization_id).try_transition(
                claim_id,
                ClaimWorkflowState.APPEAL_GENERATED,
                actor_id=requested_by,
                reason="AI appeal draft generated",
            )
            db.commit()
        except Exception:
            db.rollback()
            logger.exception(
                "AppealGeneratedHandler failed for appeal %s",
                appeal_id,
            )
        finally:
            db.close()
