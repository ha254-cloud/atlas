"""
DecisionService — evaluates a claim through the Decision Engine
(app.decisions.scoring.DecisionEngine) and persists the result as a
ClaimDecision row.

Reuses signals already computed by the Sprint 4 multi-agent pipeline and
existing deterministic engines rather than making a new AI call for every
evaluation:
  - claim.recovery_probability / claim.ai_risk_score       (ClaimAnalyzer)
  - ClaimAnalysis.confidence_score                         (ClaimAnalyzer)
  - ClaimAnalysis.multi_agent_result["risk"]["estimated_effort"]  (RiskAgent, if present)
  - DenialCode KB (required_documents, typical_resolution_days) via
    ClaimContext.denial_code_info                          (app.agents.context)
  - check_timely_filing / check_authorization              (app.validation.rules,
    same functions + same "blocking" semantics as ComplianceAgent)
  - PayerStatistics                                        (this sprint)
"""

from datetime import date

from sqlalchemy.orm import Session

from app.agents.context import build_context
from app.claims.timeline import ClaimTimeline
from app.decisions.scoring import DecisionEngine, DecisionInput
from app.models.claim import Claim
from app.models.claim_decision import ClaimDecision, DecisionAction
from app.models.claim_event import ClaimEventType
from app.models.denial import DenialType
from app.models.payer_statistics import PayerStatistics
from app.models.recovery_case import RecoveryCase, RecoveryStatus
from app.validation.rules import check_authorization, check_timely_filing


class DecisionService:
    def __init__(self, db: Session, organization_id: int):
        self.db = db
        self.organization_id = organization_id
        self.engine = DecisionEngine()

    def evaluate_claim(self, claim_id: int) -> ClaimDecision:
        context = build_context(self.db, self.organization_id, claim_id)
        claim = context.claim

        balance = claim.billed_amount - claim.paid_amount
        if balance < 0:
            balance = type(balance)(0)

        recovery_probability_pct = (
            float(claim.recovery_probability) if claim.recovery_probability is not None else 50.0
        )

        analysis = context.analysis
        ai_confidence_pct = (
            float(analysis.confidence_score)
            if analysis and analysis.confidence_score is not None
            else 50.0
        )

        analyst_effort = "medium"
        if analysis and analysis.multi_agent_result:
            risk_output = (analysis.multi_agent_result or {}).get("risk") or {}
            analyst_effort = risk_output.get("estimated_effort", analyst_effort)

        documentation_gaps: list = []
        required_documents = (context.denial_code_info or {}).get("required_documents") or []
        if required_documents and not claim.authorization_number:
            documentation_gaps = list(required_documents)

        awaiting_authorization = (
            context.denial is not None
            and context.denial.denial_type == DenialType.PRIOR_AUTH
            and not claim.authorization_number
        )

        compliance_blocking = bool(check_timely_filing(claim)) or bool(check_authorization(claim))

        days_until_deadline = self._days_until_deadline(context)

        payer_stats = (
            self.db.query(PayerStatistics)
            .filter(
                PayerStatistics.organization_id == self.organization_id,
                PayerStatistics.payer_id == claim.payer_id,
            )
            .first()
        )
        payer_avg_payment_days = (
            float(payer_stats.average_payment_time)
            if payer_stats and payer_stats.average_payment_time is not None
            else None
        )

        result = self.engine.evaluate(
            DecisionInput(
                balance=balance,
                recovery_probability_pct=recovery_probability_pct,
                ai_confidence_pct=ai_confidence_pct,
                analyst_effort=analyst_effort,
                days_until_deadline=days_until_deadline,
                payer_avg_payment_days=payer_avg_payment_days,
                documentation_gaps=documentation_gaps,
                awaiting_authorization=awaiting_authorization,
                compliance_blocking=compliance_blocking,
            )
        )

        decision = ClaimDecision(
            organization_id=self.organization_id,
            claim_id=claim_id,
            decision_score=result.decision_score,
            expected_roi=result.expected_roi,
            potential_recovery=result.potential_recovery,
            estimated_effort_cost=result.estimated_effort_cost,
            recommended_action=DecisionAction(result.recommended_action),
            reasoning=result.reasoning,
            confidence=result.confidence,
        )
        self.db.add(decision)
        self.db.commit()
        self.db.refresh(decision)

        ClaimTimeline(self.db).record(
            organization_id=self.organization_id,
            claim_id=claim_id,
            event_type=ClaimEventType.DECISION_GENERATED,
            description=(
                f"Decision engine recommended: {decision.recommended_action.value} "
                f"(score {decision.decision_score})"
            ),
            metadata={"decision_id": decision.id, "decision_score": float(decision.decision_score)},
        )
        self.db.commit()

        return decision

    def _days_until_deadline(self, context) -> int | None:
        if context.denial is None:
            return None
        resolution_days = (context.denial_code_info or {}).get("typical_resolution_days")
        if resolution_days is None or context.denial.created_at is None:
            return None
        elapsed = (date.today() - context.denial.created_at.date()).days
        return int(resolution_days) - elapsed

    def evaluate_open_claims(self, limit: int = 200) -> list[ClaimDecision]:
        claim_ids = (
            self.db.query(RecoveryCase.claim_id)
            .join(Claim, Claim.id == RecoveryCase.claim_id)
            .filter(
                RecoveryCase.organization_id == self.organization_id,
                RecoveryCase.status.in_(
                    [RecoveryStatus.OPEN, RecoveryStatus.IN_PROGRESS, RecoveryStatus.APPEALED]
                ),
            )
            .distinct()
            .limit(limit)
            .all()
        )
        return [self.evaluate_claim(cid) for (cid,) in claim_ids]

    def get_latest_for_claim(self, claim_id: int) -> ClaimDecision | None:
        return (
            self.db.query(ClaimDecision)
            .filter(
                ClaimDecision.organization_id == self.organization_id,
                ClaimDecision.claim_id == claim_id,
            )
            .order_by(ClaimDecision.id.desc())
            .first()
        )
