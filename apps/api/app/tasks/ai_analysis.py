import asyncio
from datetime import UTC, datetime
from decimal import Decimal

from app.ai.cost_tracking import ai_call_context
from app.claims.repository import ClaimRepository
from app.claims.timeline import ClaimTimeline
from app.db.database import get_db
from app.events.event_types import EventType
from app.events.publisher import EventPublisher
from app.models.claim import ClaimPriority
from app.models.claim_analysis import AnalysisStatus
from app.models.claim_event import ClaimEventType
from app.repositories.claim_analysis import ClaimAnalysisRepository
from app.services.ai.analysis_service import AIAnalysisService
from app.workers.celery_app import celery


@celery.task(
    name="tasks.analyze_claim",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    retry_kwargs={"max_retries": 3},
)
def analyze_claim_task(self, claim_id: int, organization_id: int):
    db = next(get_db())
    analysis_repository = ClaimAnalysisRepository(db, organization_id)
    timeline = ClaimTimeline(db)

    try:
        claim_repository = ClaimRepository(db, organization_id)
        claim = claim_repository.get(claim_id)
        if claim is None:
            return None

        analysis_repository.set_status(claim_id, AnalysisStatus.RUNNING)
        if self.request.retries == 0:
            timeline.record(
                organization_id=organization_id,
                claim_id=claim_id,
                event_type=ClaimEventType.ANALYSIS_STARTED,
                description="AI analysis started",
            )
            db.commit()

        service = AIAnalysisService()
        with ai_call_context(
            organization_id=organization_id,
            claim_id=claim_id,
        ):
            result = asyncio.run(service.analyze(claim))
        analysis = analysis_repository.save(
            claim_id=claim_id,
            result=result,
            model=service.model,
            prompt_version=service.prompt_version,
        )

        claim_repository.update(
            claim_id,
            ai_risk_score=Decimal(str(result.risk_score)),
            recovery_probability=(Decimal(str(result.recovery_probability)) * 100).quantize(
                Decimal("0.01")
            ),
            priority=ClaimPriority(result.priority),
        )
        timeline.record(
            organization_id=organization_id,
            claim_id=claim_id,
            event_type=ClaimEventType.ANALYZED,
            description="AI claim analysis completed",
            metadata={
                "risk_score": result.risk_score,
                "priority": result.priority.upper(),
                "confidence": result.confidence,
            },
        )
        db.commit()

        EventPublisher().publish(
            EventType.CLAIM_ANALYZED,
            {
                "claim_id": claim_id,
                "analysis_id": analysis.id,
                "organization_id": organization_id,
            },
        )
        return analysis.id
    except Exception as exc:
        db.rollback()
        if self.request.retries >= self.max_retries:
            analysis_repository.set_status(claim_id, AnalysisStatus.FAILED)
            timeline.record(
                organization_id=organization_id,
                claim_id=claim_id,
                event_type=ClaimEventType.AI_ANALYSIS_FAILED,
                description="AI claim analysis failed after retries",
                metadata={
                    "error_type": type(exc).__name__,
                    "retry_count": self.request.retries,
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            )
            db.commit()
        raise
    finally:
        db.close()
