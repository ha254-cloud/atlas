"""
Recovery Agent — produces a *strategy*, not just a score. Given the
Risk Agent's assessment and the Compliance Agent's findings (read from
`context.agent_outputs`, populated by the orchestrator after phase 1),
decides which one action makes sense:

    appeal | medical_review | phone_follow_up | provider_letter | write_off

Not every claim should be appealed — sometimes the right answer really
is "don't spend time on this claim", which the RecoveryEngine's
pre-existing `next_action` (always the same hardcoded string) never
expressed. This is the genuine, previously-missing decision logic.

Reuses the existing RecoveryEngine (app.recovery.engine) for the
score/estimated-recovery/priority math — this agent only adds the
action-selection layer on top.
"""

import time
from datetime import date

from app.agents.base import BaseAgent
from app.agents.models import AgentResult
from app.recovery.engine import RecoveryEngine

# Below this outstanding balance, even a moderate recovery probability
# isn't worth a phone call — a written provider letter (cheaper, async)
# is the more efficient next step.
PHONE_FOLLOW_UP_MIN_BALANCE = 500


class RecoveryAgent(BaseAgent):
    name = "recovery"

    def __init__(self, db=None, organization_id=None, ai_engine=None):
        super().__init__(db, organization_id, ai_engine)
        self._engine = RecoveryEngine()

    async def run(self, context) -> AgentResult:
        start = time.monotonic()
        try:
            claim = context.claim
            risk = context.agent_outputs.get("risk", {})
            compliance = context.agent_outputs.get("compliance", {})
            recovery_probability = risk.get("recovery_probability_pct", 0) / 100
            balance = claim.billed_amount - claim.paid_amount
            age_days = (date.today() - claim.service_date).days

            opportunity = self._engine.analyze(
                claim,
                denial_probability=recovery_probability,
                claim_age_days=age_days,
            )
            action, reason = self._decide_action(
                compliance, opportunity, recovery_probability, balance
            )

            output = {
                "recommended_action": action,
                "reason": reason,
                "score": float(opportunity.score) if opportunity else 0.0,
                "estimated_recovery": float(opportunity.estimated_recovery) if opportunity else 0.0,
                "priority": opportunity.priority.value if opportunity else "low",
            }
            status, error = "succeeded", None
        except Exception as exc:
            output = {
                "recommended_action": "write_off",
                "reason": "Recovery strategy could not be computed — defaulting to no action.",
                "score": 0.0,
                "estimated_recovery": 0.0,
                "priority": "low",
            }
            status, error = "failed", str(exc)

        return AgentResult(
            agent=self.name,
            output=output,
            duration_ms=int((time.monotonic() - start) * 1000),
            status=status,
            error=error,
        )

    def _decide_action(
        self, compliance: dict, opportunity, recovery_probability: float, balance
    ) -> tuple[str, str]:
        if compliance.get("blocking"):
            return (
                "write_off",
                "Compliance Agent found a blocking issue (timely filing or authorization) — "
                "recovery is unlikely to succeed regardless of risk assessment.",
            )
        if opportunity is None:
            return (
                "write_off",
                "Outstanding balance is too small or the claim is too old to justify recovery effort.",
            )
        if recovery_probability >= 0.7:
            return "appeal", "High recovery probability with no compliance blockers."
        if recovery_probability >= 0.4:
            return (
                "medical_review",
                "Moderate recovery probability — needs clinical review before deciding.",
            )
        if float(balance) >= PHONE_FOLLOW_UP_MIN_BALANCE:
            return (
                "phone_follow_up",
                "Lower probability, but the balance still justifies a follow-up call.",
            )
        return (
            "provider_letter",
            "Low recovery probability and low dollar value — a provider letter is the lowest-effort next step.",
        )
