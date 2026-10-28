"""
Structured AI response schemas.

Defines the exact shape every AI Gateway JSON response is expected to
have, per task. Kept in lockstep with the corresponding prompt template
in app/ai/prompts/ — if you change what fields a prompt asks the model
to return, update the matching schema here too.

These are intentionally used as a best-effort, log-only validation layer
(see app/ai/claim_analyzer.py) rather than a hard gate: AI output is
inherently unreliable, and ClaimAnalyzer's own normalization already
guarantees safe defaults/clamped ranges for every field before a result
is returned to callers. Validating against these schemas after that
normalization catches unexpected shape drift (e.g. a prompt change that
adds/renames a field) without risking a validation error taking down an
otherwise-recoverable AI call.
"""

from pydantic import BaseModel, Field


class ClaimAnalysisAIResponse(BaseModel):
    """
    Matches the real fields ClaimAnalyzer/`claim_analysis.md` produce
    today (denial_cause/confidence/recovery_probability/explanation/
    recommended_corrections) — NOT the generic risk_score/priority/
    recommended_action example shape from the original tutorial spec,
    which doesn't match what this codebase's prompt actually asks for.
    """

    denial_cause: str
    confidence: float = Field(ge=0.0, le=1.0)
    recovery_probability: float = Field(ge=0.0, le=1.0)
    explanation: str
    recommended_corrections: list[str] = Field(default_factory=list)
