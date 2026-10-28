"""
Compliance Agent — answers exactly one question: are there regulatory/
procedural blockers to recovering this claim? (Timely filing, prior
authorization expiration, and payer eligibility.) Nothing else — it does
not assess coding, documentation, or risk.

Timely filing / authorization checks reuse the existing deterministic
validation rules (app.validation.rules) — Claim and CanonicalClaim share
the same `service_date`/`authorization_expiration` attribute names, so
these run unmodified against a real Claim row. NOTE: unlike the
import-time Validation Engine (which treats timely filing as a
non-blocking *warning*), this agent treats it as blocking for recovery-
strategy purposes — pursuing an appeal past the filing window is rarely
productive, so downstream agents (Recovery) should not recommend one.

Eligibility is a genuinely new capability: `task="eligibility"` and
app/ai/prompts/eligibility.md already existed (pre-scaffolded, unused)
— this agent is the first real caller.
"""

import logging
import time

from app.agents.base import BaseAgent
from app.agents.models import AgentResult
from app.ai.gateway import gateway
from app.ai.prompt_loader import load_prompt
from app.validation.rules import check_authorization, check_timely_filing

logger = logging.getLogger(__name__)

ELIGIBILITY_SYSTEM_PROMPT = load_prompt("eligibility")


class ComplianceAgent(BaseAgent):
    name = "compliance"

    async def run(self, context) -> AgentResult:
        start = time.monotonic()
        try:
            claim = context.claim
            issues = [self._to_dict(i) for i in check_timely_filing(claim)]
            issues += [self._to_dict(i) for i in check_authorization(claim)]

            timely_filing_ok = not any(i["code"] == "TIMELY_FILING_RISK" for i in issues)
            authorization_ok = not any(i["code"] == "AUTHORIZATION_EXPIRED" for i in issues)
            blocking = not timely_filing_ok or not authorization_ok

            eligibility = await self._check_eligibility(context)

            output = {
                "issues": issues,
                "blocking": blocking,
                "timely_filing_ok": timely_filing_ok,
                "authorization_ok": authorization_ok,
                "eligibility": eligibility,
            }
            status, error = "succeeded", None
        except Exception as exc:
            logger.exception("Compliance agent failed for claim %s", context.claim.id)
            output = {
                "issues": [],
                "blocking": False,
                "timely_filing_ok": True,
                "authorization_ok": True,
                "eligibility": None,
            }
            status, error = "failed", str(exc)

        return AgentResult(
            agent=self.name,
            output=output,
            duration_ms=int((time.monotonic() - start) * 1000),
            status=status,
            error=error,
        )

    def _to_dict(self, issue) -> dict:
        return {
            "code": issue.code,
            "severity": issue.severity,
            "field": issue.field,
            "message": issue.message,
        }

    async def _check_eligibility(self, context) -> dict | None:
        """Only worth asking when there's an actual denial to reason about
        — skips a pointless AI call (and cost) otherwise."""
        if context.denial is None:
            return None
        try:
            claim = context.claim
            prompt = (
                f"Claim Number: {claim.claim_number}\n"
                f"Patient ID: {context.patient.id if context.patient else 'Unknown'}\n"
                f"Payer: {context.payer.name if context.payer else 'Unknown'}\n"
                f"Service Date: {claim.service_date}\n"
                f"Procedure Codes: {', '.join(line.cpt_code for line in claim.claim_lines) or 'None on file'}\n"
                f"Denial Code: {context.denial.denial_code}\n"
                f"Denial Reason: {context.denial.description or 'Not specified'}\n"
            )
            raw = await gateway.generate_json(
                task="eligibility", prompt=prompt, system=ELIGIBILITY_SYSTEM_PROMPT
            )
            if not isinstance(raw, dict) or "error" in raw:
                return None
            return {
                "eligibility_status": str(raw.get("eligibility_status", "unknown")),
                "issues": raw.get("issues") if isinstance(raw.get("issues"), list) else [],
                "summary": str(raw.get("summary", "")),
            }
        except Exception:
            logger.exception("Eligibility check failed for claim %s", context.claim.id)
            return None
