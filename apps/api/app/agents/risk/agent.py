"""
Risk Agent — answers exactly one question: how risky/valuable is this
claim, and how much effort will it take? (Risk score, recovery
probability, priority, expected recovery, estimated effort.)

Reuses ClaimAnalyzer (app.ai.claim_analyzer) — the same single LLM call
already used by the standard analyze-on-import pipeline
(ClaimAnalysisService) — rather than adding a second, redundant AI call
for the same underlying question. This means running the multi-agent
orchestration on a claim that was already analyzed re-invokes the LLM
(no caching yet, see Sprint 2 notes) — a deliberate, known tradeoff, not
an oversight.
"""

import time
from decimal import Decimal

from app.agents.base import BaseAgent
from app.agents.models import AgentResult
from app.ai.claim_analyzer import ClaimAnalyzer

FALLBACK_OUTPUT = {
    "risk_score": 100.0,
    "recovery_probability_pct": 0.0,
    "priority": "low",
    "expected_recovery": 0.0,
    "estimated_effort": "high",
    "denial_cause": "unknown",
    "confidence_pct": 0.0,
    "explanation": "Risk assessment is unavailable for this claim right now.",
    "recommended_corrections": [],
}


class RiskAgent(BaseAgent):
    name = "risk"

    async def run(self, context) -> AgentResult:
        # Local import avoids a module import cycle (claim_analysis_service
        # -> app.agents would otherwise be circular if imported at module
        # scope, since agents live under app.agents and are orchestrated
        # independently of that service).
        from app.services.claim_analysis_service import _priority_from_risk_score

        start = time.monotonic()
        try:
            analyzer = ClaimAnalyzer(self.ai_engine)
            result = await analyzer.analyze(context.claim, context.denial_code_info)

            recovery_probability = float(result["recovery_probability"])
            risk_score = round((1 - recovery_probability) * 100, 2)
            balance = context.claim.billed_amount - context.claim.paid_amount
            expected_recovery = round(float(balance) * recovery_probability, 2)
            priority = _priority_from_risk_score(Decimal(str(risk_score))).value

            output = {
                "risk_score": risk_score,
                "recovery_probability_pct": round(recovery_probability * 100, 2),
                "priority": priority,
                "expected_recovery": expected_recovery,
                "estimated_effort": self._estimate_effort(result),
                "denial_cause": result["denial_cause"],
                "confidence_pct": round(float(result["confidence"]) * 100, 2),
                "explanation": result["explanation"],
                "recommended_corrections": result["recommended_corrections"],
            }
            status, error = "succeeded", None
        except Exception as exc:
            output, status, error = dict(FALLBACK_OUTPUT), "failed", str(exc)

        return AgentResult(
            agent=self.name,
            output=output,
            duration_ms=int((time.monotonic() - start) * 1000),
            status=status,
            error=error,
        )

    def _estimate_effort(self, result: dict) -> str:
        confidence = float(result["confidence"])
        corrections = len(result["recommended_corrections"])
        if confidence >= 0.7 and corrections <= 1:
            return "low"
        if corrections <= 3:
            return "medium"
        return "high"
