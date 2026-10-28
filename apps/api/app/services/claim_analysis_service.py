"""
ClaimAnalysisService — the single entry point for AI claim analysis.

Responsibilities (per the Recovery Intelligence Engine design):
  - Build the AI prompt (delegated to ClaimAnalyzer)
  - Call the LLM (delegated to ClaimAnalyzer -> AIEngine)
  - Parse/normalize the response (delegated to ClaimAnalyzer)
  - Save structured results (this class — AIAnalysis audit row +
    upserted ClaimAnalysis row + Claim score columns + Denial category)
  - Queue follow-up work (recovery re-scoring, auto-drafted appeal,
    timeline event, CLAIM_ANALYZED event)

Nothing else in the codebase should call the AI provider directly for
claim analysis — routes/tasks call this service instead.
"""

import logging
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.ai.claim_analyzer import ClaimAnalyzer, denial_cause_to_type
from app.ai.cost_tracking import ai_call_context
from app.ai.engine import AIEngine
from app.appeals.service import AppealService
from app.claims.timeline import ClaimTimeline
from app.events.event_types import EventType
from app.events.publisher import EventPublisher
from app.models.ai_analysis import AIAnalysis
from app.models.claim import Claim, ClaimPriority
from app.models.claim_analysis import AnalysisStatus, ClaimAnalysis
from app.models.claim_event import ClaimEventType
from app.models.claim_workflow import ClaimWorkflowState
from app.models.denial import Denial
from app.models.recovery_case import RecoveryCase
from app.recovery.engine import RecoveryEngine
from app.repositories.denial_code_repository import DenialCodeRepository
from app.workflows.service import WorkflowService

logger = logging.getLogger(__name__)

# A recovery case is only worth auto-drafting an appeal for once the AI
# thinks there's a better-than-even chance it succeeds — below that, a
# human should decide whether it's worth pursuing at all.
AUTO_APPEAL_THRESHOLD = 0.5


def _priority_from_risk_score(ai_risk_score: Decimal) -> ClaimPriority:
    """Map the AI's risk score (0-100, higher = more likely to need
    intervention) onto the claim's triage Priority.

    This is intentionally separate from the other two priority-like
    calculations already in the codebase — RecoveryEngine._determine_priority
    (recovery/engine.py, ranks a *RecoveryCase* by score + dollar balance)
    and compute_priority_score (workflows/priority.py, ranks workflow queue
    items) — those answer "how urgent is this piece of work", while this
    one exists purely so Claim.priority reflects the AI's own risk
    assessment for anyone filtering/sorting the claims list by it.
    """
    if ai_risk_score >= Decimal("80"):
        return ClaimPriority.CRITICAL
    if ai_risk_score >= Decimal("60"):
        return ClaimPriority.HIGH
    if ai_risk_score >= Decimal("30"):
        return ClaimPriority.MEDIUM
    return ClaimPriority.LOW


class ClaimAnalysisService:
    def __init__(self, db: Session, organization_id: int, ai_engine: AIEngine | None = None):
        self.db = db
        self.organization_id = organization_id
        self.analyzer = ClaimAnalyzer(ai_engine)
        self.recovery_engine = RecoveryEngine()
        self.publisher = EventPublisher()

    async def analyze_and_store(self, claim) -> ClaimAnalysis:
        """Run AI analysis on `claim`, persist every downstream effect, and
        return the resulting ClaimAnalysis row."""
        denial_code_info = self._lookup_denial_code_info(claim)
        extra_context = self._build_extra_context(claim)

        ClaimTimeline(self.db).record(
            organization_id=self.organization_id,
            claim_id=claim.id,
            event_type=ClaimEventType.ANALYSIS_STARTED,
            description="AI analysis started",
        )

        try:
            with ai_call_context(organization_id=self.organization_id, claim_id=claim.id):
                result = await self.analyzer.analyze(claim, denial_code_info, extra_context)
        except Exception:
            # Record the failure so it's visible immediately, then re-raise —
            # the caller (analyze_claim_task) is configured to auto-retry on
            # exception, and re-running this method for the same claim is
            # safe: _store_failed/_upsert_analysis both upsert by claim_id.
            logger.exception("AI analysis failed for claim %s", claim.id)
            self._store_failed(claim)
            raise

        ai_analysis = self._store_raw(claim, result)
        self._update_claim_scores(claim, result)
        denial_type = self._classify_denial(claim, result)
        analysis = self._upsert_analysis(claim, result, denial_type, ai_analysis)

        ClaimTimeline(self.db).record(
            organization_id=self.organization_id,
            claim_id=claim.id,
            event_type=ClaimEventType.ANALYZED,
            description=f"AI analysis completed — predicted cause: {result['denial_cause']}",
            metadata={"analysis_id": ai_analysis.id, **result},
        )

        WorkflowService(self.db, self.organization_id).try_transition(
            claim.id,
            ClaimWorkflowState.ANALYZED,
            reason=f"AI analysis completed — predicted cause: {result['denial_cause']}",
        )

        recovery_probability = float(result["recovery_probability"])
        recovery_case = self._rescore_recovery_case(claim, recovery_probability, result)

        if recovery_case is not None and recovery_probability >= AUTO_APPEAL_THRESHOLD:
            await self._auto_draft_appeal(claim, recovery_case)

        self.publisher.publish(
            EventType.CLAIM_ANALYZED,
            {
                "claim_id": claim.id,
                "analysis_id": ai_analysis.id,
                "organization_id": self.organization_id,
            },
        )

        return analysis

    def _lookup_denial_code_info(self, claim) -> dict | None:
        """Ground the analyzer's prompt in Atlas' denial knowledge base, if
        the claim has a denial with a recognized code."""
        denial = (
            self.db.query(Denial)
            .filter(Denial.claim_id == claim.id, Denial.organization_id == self.organization_id)
            .order_by(Denial.id.desc())
            .first()
        )
        if denial is None:
            return None

        entry = DenialCodeRepository(self.db).get_by_code(denial.denial_code)
        if entry is None:
            return None

        return {
            "code": entry.code,
            "category": entry.category.value,
            "description": entry.description,
            "recovery_strategy": entry.recovery_strategy,
            "ai_guidance": entry.ai_guidance,
            "severity": entry.severity.value if entry.severity else None,
            "recoverability": entry.recoverability.value if entry.recoverability else None,
            "typical_recovery_rate": entry.typical_recovery_rate,
            "required_documents": entry.required_documents,
            "typical_resolution_days": entry.typical_resolution_days,
            "common_payers": entry.common_payers,
        }

    def _build_extra_context(self, claim) -> dict:
        """Richer context for the AI prompt beyond the bare claim fields —
        payer, diagnoses, procedures, patient age, and prior denial history
        for this patient — all sourced from relationships ClaimRepository
        already eager-loads (see app/claims/repository.py), so this adds
        no extra queries beyond the prior-denials count and the current
        denial's raw description."""
        extra: dict = {}

        if claim.payer is not None:
            extra["payer_name"] = claim.payer.name

        if claim.diagnoses:
            extra["diagnosis_codes"] = [d.icd_code for d in claim.diagnoses]

        if claim.claim_lines:
            extra["procedure_codes"] = list(
                dict.fromkeys(line.cpt_code for line in claim.claim_lines)
            )

        if claim.patient is not None and claim.patient.date_of_birth is not None:
            dob = claim.patient.date_of_birth
            today = date.today()
            extra["patient_age"] = (
                today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
            )

        latest_denial = (
            self.db.query(Denial)
            .filter(Denial.claim_id == claim.id, Denial.organization_id == self.organization_id)
            .order_by(Denial.id.desc())
            .first()
        )
        if latest_denial is not None:
            extra["denial_reason"] = latest_denial.description

        if getattr(claim, "patient_id", None):
            extra["previous_denials"] = (
                self.db.query(Denial)
                .join(Claim, Claim.id == Denial.claim_id)
                .filter(
                    Claim.patient_id == claim.patient_id,
                    Claim.id != claim.id,
                    Denial.organization_id == self.organization_id,
                )
                .count()
            )

        return extra

    def _store_raw(self, claim, result: dict) -> AIAnalysis:
        ai_analysis = AIAnalysis(
            organization_id=self.organization_id,
            claim_id=claim.id,
            provider="openai",
            model="gpt-4.1",
            result=result,
        )
        self.db.add(ai_analysis)
        self.db.commit()
        self.db.refresh(ai_analysis)
        return ai_analysis

    def _update_claim_scores(self, claim, result: dict) -> None:
        recovery_probability = Decimal(str(result["recovery_probability"]))
        claim.recovery_probability = (recovery_probability * 100).quantize(Decimal("0.01"))
        claim.ai_risk_score = ((Decimal("1") - recovery_probability) * 100).quantize(
            Decimal("0.01")
        )
        claim.priority = _priority_from_risk_score(claim.ai_risk_score)
        self.db.commit()
        self.db.refresh(claim)

    def _classify_denial(self, claim, result: dict):
        """Map the AI's predicted denial_cause onto the standardized
        DenialType and update the claim's most recent Denial row, if any."""
        denial_type = denial_cause_to_type(result["denial_cause"])
        denial = (
            self.db.query(Denial)
            .filter(Denial.claim_id == claim.id, Denial.organization_id == self.organization_id)
            .order_by(Denial.id.desc())
            .first()
        )
        if denial is not None:
            denial.denial_type = denial_type
            self.db.commit()
        return denial_type

    def _upsert_analysis(
        self, claim, result: dict, denial_type, ai_analysis: AIAnalysis
    ) -> ClaimAnalysis:
        balance = claim.billed_amount - claim.paid_amount
        recovery_probability = Decimal(str(result["recovery_probability"]))
        estimated_recovery_amount = (balance * recovery_probability).quantize(Decimal("0.01"))
        recommended_action = "; ".join(result["recommended_corrections"]) or None

        analysis = self.db.query(ClaimAnalysis).filter(ClaimAnalysis.claim_id == claim.id).first()
        if analysis is None:
            analysis = ClaimAnalysis(organization_id=self.organization_id, claim_id=claim.id)
            self.db.add(analysis)

        analysis.analysis_status = AnalysisStatus.COMPLETED
        analysis.denial_category = denial_type.value
        analysis.root_cause = result["denial_cause"]
        analysis.recovery_probability = (recovery_probability * 100).quantize(Decimal("0.01"))
        analysis.estimated_recovery_amount = estimated_recovery_amount
        analysis.recommended_action = recommended_action
        analysis.confidence_score = (Decimal(str(result["confidence"])) * 100).quantize(
            Decimal("0.01")
        )
        analysis.ai_summary = result["explanation"]
        analysis.model_version = ai_analysis.model
        analysis.needs_review = bool(result.get("needs_review", False))

        self.db.commit()
        self.db.refresh(analysis)
        return analysis

    def _rescore_recovery_case(self, claim, recovery_probability: float, result: dict):
        recovery_case = (
            self.db.query(RecoveryCase)
            .filter(
                RecoveryCase.claim_id == claim.id,
                RecoveryCase.organization_id == self.organization_id,
            )
            .order_by(RecoveryCase.id.desc())
            .first()
        )
        if recovery_case is None:
            return None

        age_days = (date.today() - claim.service_date).days
        opportunity = self.recovery_engine.analyze(
            claim,
            denial_probability=recovery_probability,
            claim_age_days=age_days,
        )
        if opportunity is None:
            return None

        recovery_case.recovery_score = opportunity.score
        recovery_case.estimated_value = opportunity.estimated_recovery
        recommendation = result["explanation"]
        if result["recommended_corrections"]:
            recommendation += " Recommended: " + "; ".join(result["recommended_corrections"])
        recovery_case.recommendation = recommendation[:1000]
        self.db.commit()
        return recovery_case

    async def _auto_draft_appeal(self, claim, recovery_case) -> None:
        try:
            await AppealService(self.db, self.organization_id).generate_appeal(
                claim.id, recovery_case.id
            )
        except Exception:
            # Appeal drafting is best-effort — the analysis itself already
            # succeeded and was persisted above.
            logger.exception("Auto-appeal drafting failed for claim %s", claim.id)

    def _store_failed(self, claim) -> ClaimAnalysis:
        analysis = self.db.query(ClaimAnalysis).filter(ClaimAnalysis.claim_id == claim.id).first()
        if analysis is None:
            analysis = ClaimAnalysis(organization_id=self.organization_id, claim_id=claim.id)
            self.db.add(analysis)
        analysis.analysis_status = AnalysisStatus.FAILED
        self.db.commit()
        self.db.refresh(analysis)
        return analysis
