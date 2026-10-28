from sqlalchemy.orm import Session

from app.ai.appeal_generator import AppealGenerator
from app.ai.claim_analyzer import ClaimAnalyzer
from app.claims.repository import ClaimRepository
from app.events.event_types import EventType
from app.events.publisher import EventPublisher
from app.models.ai_analysis import AIAnalysis
from app.models.claim import Claim
from app.models.recovery_case import RecoveryCase, RecoveryStatus


class AtlasOrchestrator:
    def __init__(self, db: Session, organization_id: int):
        self.db = db
        self.organization_id = organization_id
        self.claim_repo = ClaimRepository(db, organization_id)
        self.publisher = EventPublisher()
        self.analyzer = ClaimAnalyzer()
        self.appeal_generator = AppealGenerator()

    async def orchestrate_claim(self, claim_id: int) -> dict:
        claim = self.claim_repo.get_by_id(claim_id)
        if not claim:
            raise ValueError(f"Claim {claim_id} not found")

        analysis = await self._run_ai_analysis(claim)
        recovery_case = self._create_recovery_case(claim)
        appeal_text = await self._generate_appeal(claim)

        self.db.commit()
        self.db.refresh(analysis)
        self.db.refresh(recovery_case)

        return {
            "claim_id": claim.id,
            "analysis_id": analysis.id,
            "recovery_case_id": recovery_case.id,
            "appeal": appeal_text,
        }

    async def _run_ai_analysis(self, claim: Claim) -> AIAnalysis:
        result = await self.analyzer.analyze(claim)

        analysis = AIAnalysis(
            claim_id=claim.id,
            provider="openai",
            model="gpt-4.1",
            result={"analysis": result},
        )

        self.db.add(analysis)
        self.db.flush()

        self.publisher.publish(
            EventType.CLAIM_ANALYZED,
            {"claim_id": claim.id, "analysis_id": analysis.id},
        )

        return analysis

    def _create_recovery_case(self, claim: Claim) -> RecoveryCase:
        recovery_case = RecoveryCase(
            claim_id=claim.id,
            recovery_score=0.0,
            estimated_value=claim.billed_amount,
            status=RecoveryStatus.OPEN,
            recommendation="Review claim and pursue recovery",
        )

        self.db.add(recovery_case)
        self.db.flush()

        self.publisher.publish(
            EventType.RECOVERY_CREATED,
            {"claim_id": claim.id, "recovery_case_id": recovery_case.id},
        )

        return recovery_case

    async def _generate_appeal(self, claim: Claim) -> str:
        appeal = await self.appeal_generator.generate_appeal(claim)

        self.publisher.publish(
            EventType.APPEAL_GENERATED,
            {"claim_id": claim.id},
        )

        return appeal
