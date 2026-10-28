"""
Appeal Agent — only writes appeals. It never calculates risk (that's the
Risk Agent) and never decides *whether* to appeal (that's the Recovery
Agent's job) — the orchestrator only invokes this agent when the
Recovery Agent recommended "appeal" and Compliance found no blocking
issue.

Wraps the existing, mature AppealService/AppealGenerator pipeline
(knowledge-base-grounded prompt, evidence checklist, human-review-gated
lifecycle) rather than making a second, parallel LLM call — this agent's
"generation" *is* that pipeline.
"""

import logging
import time

from app.agents.base import BaseAgent
from app.agents.models import AgentResult
from app.appeals.service import AppealService

logger = logging.getLogger(__name__)


class AppealAgent(BaseAgent):
    name = "appeal"

    async def run(self, context) -> AgentResult:
        start = time.monotonic()
        try:
            recovery_case_id = context.recovery_case.id if context.recovery_case else None
            appeal = await AppealService(self.db, self.organization_id).generate_appeal(
                context.claim.id,
                recovery_case_id,
            )
            output = {
                "appeal_id": appeal.id,
                "status": appeal.status.value,
                "summary": appeal.summary,
                "missing_documents": appeal.missing_documents or [],
            }
            status, error = "succeeded", None
        except Exception as exc:
            logger.exception("Appeal agent failed for claim %s", context.claim.id)
            output = {
                "appeal_id": None,
                "status": "failed",
                "summary": None,
                "missing_documents": [],
            }
            status, error = "failed", str(exc)

        return AgentResult(
            agent=self.name,
            output=output,
            duration_ms=int((time.monotonic() - start) * 1000),
            status=status,
            error=error,
        )
