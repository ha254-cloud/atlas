"""
Documentation Agent — answers exactly one question: is the required
supporting documentation on file for this claim? (Missing operative
report, referral, clinical notes, authorization, labs, imaging, etc.)

Deliberately reuses the existing EvidenceCollector (app.appeals.evidence)
instead of adding a new LLM call: EvidenceCollector already cross-
references the denial code's knowledge-base `required_documents` against
what Atlas can verify is on file (uploaded Evidence Library documents,
falling back to structural claim data) — exactly this agent's job, for
free and deterministically. A `documentation.md` AI prompt also exists
in app/ai/prompts/ but is a different, pre-existing (and currently
unused-by-this-agent) free-text deficiency-analysis template — see
repo memory for the naming overlap with app.documents.service's
unrelated "summarize a document" task, which also uses task="documentation".
"""

import time

from app.agents.base import BaseAgent
from app.agents.models import AgentResult
from app.appeals.evidence import EvidenceCollector


class DocumentationAgent(BaseAgent):
    name = "documentation"

    async def run(self, context) -> AgentResult:
        start = time.monotonic()
        try:
            check = EvidenceCollector().check(
                context.claim, context.denial_code_info, context.documents
            )
            completeness = (
                round(len(check.verified) / len(check.required) * 100, 1)
                if check.required
                else 100.0
            )
            output = {
                "required_documents": check.required,
                "verified_documents": check.verified,
                "missing_documents": check.needs_verification,
                "completeness_score": completeness,
                "is_complete": check.is_complete,
            }
            status, error = "succeeded", None
        except Exception as exc:
            output = {
                "required_documents": [],
                "verified_documents": [],
                "missing_documents": [],
                "completeness_score": 0.0,
                "is_complete": False,
            }
            status, error = "failed", str(exc)

        return AgentResult(
            agent=self.name,
            output=output,
            duration_ms=int((time.monotonic() - start) * 1000),
            status=status,
            error=error,
        )
