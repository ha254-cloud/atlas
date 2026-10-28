"""
Coding Agent — answers exactly one question: is this claim coded
correctly? (Incorrect ICD/CPT, missing modifiers, medical necessity of
the codes billed, and an overall coding-confidence/resubmit signal.)

Genuinely new capability: the `task="coding"` AI Gateway route and
app/ai/prompts/coding.md prompt template already existed (pre-scaffolded
in an earlier round) but had ZERO call sites anywhere in the codebase —
this agent is the first thing that actually uses them.
"""

import logging
import time

from app.agents.base import BaseAgent
from app.agents.models import AgentResult
from app.ai.gateway import gateway
from app.ai.prompt_loader import load_prompt

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = load_prompt("coding")

FALLBACK_OUTPUT = {
    "issues": [],
    "confidence": 0,
    "summary": "Coding review is unavailable for this claim right now.",
    "resubmit_recommended": False,
}


class CodingAgent(BaseAgent):
    name = "coding"

    async def run(self, context) -> AgentResult:
        start = time.monotonic()
        try:
            output = self._normalize(await self._call(context))
            status, error = "succeeded", None
        except Exception as exc:
            logger.exception("Coding agent failed for claim %s", context.claim.id)
            output, status, error = dict(FALLBACK_OUTPUT), "failed", str(exc)

        return AgentResult(
            agent=self.name,
            output=output,
            duration_ms=int((time.monotonic() - start) * 1000),
            status=status,
            error=error,
        )

    async def _call(self, context) -> dict:
        claim = context.claim
        procedure_codes = ", ".join(line.cpt_code for line in claim.claim_lines) or "None on file"
        diagnosis_codes = ", ".join(d.icd_code for d in claim.diagnoses) or "None on file"
        modifiers = (
            ", ".join(line.modifier for line in claim.claim_lines if line.modifier)
            or "None on file"
        )
        payer_name = context.payer.name if context.payer else "Unknown"

        prompt = (
            f"Procedure Codes: {procedure_codes}\n"
            f"Diagnosis Codes: {diagnosis_codes}\n"
            f"Modifiers: {modifiers}\n"
            f"Payer: {payer_name}\n"
            f"Service Date: {claim.service_date}\n"
        )
        return await gateway.generate_json(task=self.name, prompt=prompt, system=SYSTEM_PROMPT)

    def _normalize(self, result: dict) -> dict:
        if not isinstance(result, dict) or "error" in result:
            return dict(FALLBACK_OUTPUT)

        issues = result.get("issues")
        normalized_issues = []
        if isinstance(issues, list):
            for item in issues:
                if isinstance(item, dict):
                    normalized_issues.append(
                        {
                            "code": str(item.get("code", "")),
                            "type": str(item.get("type", "")),
                            "description": str(item.get("description", "")),
                            "recommended_fix": str(item.get("recommended_fix", "")),
                        }
                    )

        try:
            confidence = max(0.0, min(100.0, float(result.get("confidence", 0))))
        except (TypeError, ValueError):
            confidence = 0.0

        return {
            "issues": normalized_issues,
            "confidence": confidence,
            "summary": str(result.get("summary", "")),
            "resubmit_recommended": bool(result.get("resubmit_recommended", False)),
        }
