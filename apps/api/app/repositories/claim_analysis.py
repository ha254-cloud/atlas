from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.claim_analysis import AnalysisStatus, ClaimAnalysis
from app.schemas.claim_analysis import ClaimAnalysisResult


class ClaimAnalysisRepository:
    def __init__(self, db: Session, organization_id: int):
        self.db = db
        self.organization_id = organization_id

    def save(
        self,
        *,
        claim_id: int,
        result: ClaimAnalysisResult,
        model: str,
        prompt_version: str,
    ) -> ClaimAnalysis:
        analysis = self._get_or_create(claim_id)
        analysis.analysis_status = AnalysisStatus.COMPLETED
        analysis.risk_score = Decimal(str(result.risk_score))
        analysis.priority = result.priority
        analysis.recovery_probability = self._as_percentage(result.recovery_probability)
        analysis.confidence_score = self._as_percentage(result.confidence)
        analysis.recommended_action = result.recommended_action
        analysis.ai_summary = result.summary
        analysis.required_documents = list(result.required_documents)
        analysis.model = model
        analysis.model_version = model
        analysis.prompt_version = prompt_version
        analysis.needs_review = False
        self.db.commit()
        self.db.refresh(analysis)
        return analysis

    def set_status(self, claim_id: int, status: AnalysisStatus) -> ClaimAnalysis:
        analysis = self._get_or_create(claim_id)
        analysis.analysis_status = status
        self.db.commit()
        self.db.refresh(analysis)
        return analysis

    def get_latest(self, claim_id: int) -> ClaimAnalysis | None:
        return (
            self.db.query(ClaimAnalysis)
            .filter(
                ClaimAnalysis.claim_id == claim_id,
                ClaimAnalysis.organization_id == self.organization_id,
            )
            .order_by(ClaimAnalysis.created_at.desc(), ClaimAnalysis.id.desc())
            .first()
        )

    def list_by_claim(self, claim_id: int) -> list[ClaimAnalysis]:
        return (
            self.db.query(ClaimAnalysis)
            .filter(
                ClaimAnalysis.claim_id == claim_id,
                ClaimAnalysis.organization_id == self.organization_id,
            )
            .order_by(ClaimAnalysis.created_at.desc(), ClaimAnalysis.id.desc())
            .all()
        )

    def _get_or_create(self, claim_id: int) -> ClaimAnalysis:
        analysis = self.get_latest(claim_id)
        if analysis is None:
            analysis = ClaimAnalysis(
                organization_id=self.organization_id,
                claim_id=claim_id,
                analysis_status=AnalysisStatus.PENDING,
            )
            self.db.add(analysis)
        return analysis

    @staticmethod
    def _as_percentage(value: float) -> Decimal:
        return (Decimal(str(value)) * 100).quantize(Decimal("0.01"))
