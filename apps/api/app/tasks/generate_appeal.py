import asyncio

from app.appeals.repository import AppealRepository
from app.claims.repository import ClaimRepository
from app.claims.timeline import ClaimTimeline
from app.db.database import get_db
from app.events.event_types import EventType
from app.events.publisher import EventPublisher
from app.models.claim_event import ClaimEventType
from app.services.ai.appeal_generation_service import AppealGenerationService
from app.workers.celery_app import celery


@celery.task(
    name="tasks.generate_appeal",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    retry_kwargs={"max_retries": 3},
)
def generate_appeal_task(
    self,
    claim_id: int,
    organization_id: int,
    appeal_id: int,
    requested_by: int,
):
    db = next(get_db())
    try:
        claim = ClaimRepository(db, organization_id).get(claim_id)
        if claim is None or claim.analysis is None:
            raise ValueError(f"Analyzed claim {claim_id} not found")

        service = AppealGenerationService()
        result = asyncio.run(service.generate(claim))
        appeal = AppealRepository(db, organization_id).save_generated(
            appeal_id,
            title=result.title,
            letter=result.letter,
            confidence=result.confidence,
            required_documents=result.required_documents,
            missing_documents=result.missing_documents,
            references=result.references,
            model=service.model,
        )
        if appeal is None:
            raise ValueError(f"Draft appeal {appeal_id} not found")

        ClaimTimeline(db).record(
            organization_id=organization_id,
            claim_id=claim_id,
            event_type=ClaimEventType.APPEAL_GENERATED,
            description="AI appeal draft generated",
            actor_id=requested_by,
            metadata={
                "appeal_id": appeal.id,
                "version": appeal.current_version,
                "model": service.model,
                "prompt_version": service.prompt_version,
            },
        )
        db.commit()

        EventPublisher().publish(
            EventType.APPEAL_GENERATED,
            {
                "appeal_id": appeal.id,
                "claim_id": claim_id,
                "organization_id": organization_id,
                "requested_by": requested_by,
                "version": appeal.current_version,
            },
        )
        return appeal.id
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
