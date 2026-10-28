"""
ClaimAnalyzer — the core of the AI Claim Recovery Engine.

Given a claim, asks the LLM for a structured assessment: a predicted denial
cause, a confidence score, a recovery probability, a plain-English
explanation, and concrete recommended corrections. The structured result
feeds directly into the recovery scoring engine (`app.recovery.engine`) and,
when the case looks promising enough, an automatically drafted appeal.
"""

import logging

from pydantic import ValidationError

from app.ai.cache import build_cache_key
from app.ai.gateway import gateway
from app.ai.prompt_loader import load_prompt
from app.ai.schemas import ClaimAnalysisAIResponse
from app.models.denial import DenialType

logger = logging.getLogger(__name__)

REQUIRED_KEYS = (
    "denial_cause",
    "confidence",
    "recovery_probability",
    "explanation",
    "recommended_corrections",
)

# Returned whenever the model is unavailable or its response can't be trusted
# (missing key, unparseable JSON, out-of-range value, etc.) — callers can
# always rely on every key being present with a safe, conservative value.
FALLBACK_RESULT = {
    "denial_cause": "unknown",
    "confidence": 0.0,
    "recovery_probability": 0.0,
    "explanation": "AI analysis is unavailable for this claim right now.",
    "recommended_corrections": [],
}

SYSTEM_PROMPT = load_prompt("claim_analysis")

# Maps the AI's `denial_cause` category onto the standardized DenialType
# enum that drives dashboards/reporting/automation. Keys mirror the exact
# categories listed in SYSTEM_PROMPT above — keep both in sync.
DENIAL_CAUSE_TO_TYPE = {
    "eligibility": DenialType.ELIGIBILITY,
    "prior_authorization": DenialType.PRIOR_AUTH,
    "coding_error": DenialType.CODING,
    "medical_necessity": DenialType.MEDICAL_NECESSITY,
    "timely_filing": DenialType.TIMELY_FILING,
    "duplicate_claim": DenialType.DUPLICATE,
    "coordination_of_benefits": DenialType.COORDINATION_OF_BENEFITS,
    "missing_documentation": DenialType.DOCUMENTATION,
    "modifier_error": DenialType.MODIFIER_ERROR,
    "non_covered_service": DenialType.NON_COVERED_SERVICE,
    "other": DenialType.OTHER,
}


def denial_cause_to_type(denial_cause: str) -> DenialType:
    """Map an AI-produced `denial_cause` string onto the standardized
    DenialType enum, defaulting to OTHER for anything unrecognized."""
    return DENIAL_CAUSE_TO_TYPE.get(denial_cause, DenialType.OTHER)


class _GatewayAIEngine:
    """
    Default AI backend for ClaimAnalyzer — routes through the AI Gateway
    (task="claim_analysis") instead of talking to a provider directly, so
    claim analysis gets the same provider routing/fallback behavior as
    every other AI feature. Tests inject their own stub via `ai_engine=`
    and never touch this class.
    """

    async def generate_json(self, prompt: str, system: str | None = None) -> dict:
        return await gateway.generate_json(task="claim_analysis", prompt=prompt, system=system)


class ClaimAnalyzer:
    def __init__(self, ai_engine=None):
        self.ai = ai_engine or _GatewayAIEngine()

    async def analyze(
        self,
        claim,
        denial_code_info: dict | None = None,
        extra_context: dict | None = None,
    ) -> dict:
        prompt = self._build_prompt(claim, denial_code_info, extra_context)

        result = await self._call_ai(claim, prompt, use_cache=True)

        if _is_invalid_raw(result):
            # The model's response was unusable (missing keys, an error
            # payload, or not a dict at all) — give it one more shot before
            # settling for the fallback. Skip the cache on the retry so we
            # don't just read back the same bad response we're trying to
            # get away from.
            logger.warning(
                "AI claim analysis returned an invalid response for claim %s — retrying once",
                getattr(claim, "id", None),
            )
            result = await self._call_ai(claim, prompt, use_cache=False)

        normalized = self._normalize(result)

        if _is_invalid_raw(result):
            # Still invalid after the retry — persist the safe fallback
            # values (as before), but flag the analysis so a human knows
            # not to trust it instead of silently treating it as a normal
            # completed analysis.
            logger.warning(
                "AI claim analysis still invalid for claim %s after retry — flagging for review",
                getattr(claim, "id", None),
            )
            normalized["needs_review"] = True

        _validate_shape(normalized)
        return normalized

    async def _call_ai(self, claim, prompt: str, use_cache: bool) -> dict:
        if isinstance(self.ai, _GatewayAIEngine):
            # Real (non-test) path only — cache key needs the claim's own
            # id/updated_at, which test doubles (StubAIEngine) never see.
            cache_key = None
            if use_cache:
                cache_key = build_cache_key(
                    task="claim_analysis",
                    claim_id=claim.id,
                    prompt_version=gateway.prompt_version_for("claim_analysis"),
                    model=gateway.model_for("claim_analysis"),
                    claim_updated_at=getattr(claim, "updated_at", None),
                )
            return await gateway.generate_json(
                task="claim_analysis", prompt=prompt, system=SYSTEM_PROMPT, cache_key=cache_key
            )
        return await self.ai.generate_json(prompt, system=SYSTEM_PROMPT)

    def _build_prompt(
        self,
        claim,
        denial_code_info: dict | None = None,
        extra_context: dict | None = None,
    ) -> str:
        balance = claim.billed_amount - claim.paid_amount
        prompt = (
            f"Claim Number: {claim.claim_number}\n"
            f"Status: {claim.status}\n"
            f"Billed Amount: {claim.billed_amount}\n"
            f"Paid Amount: {claim.paid_amount}\n"
            f"Outstanding Balance: {balance}\n"
            f"Service Date: {claim.service_date}\n"
        )

        # Ground the model in Atlas' denial knowledge base instead of
        # asking it to recall from memory what a payer denial code means —
        # this keeps classification consistent and lets us improve
        # accuracy just by editing the knowledge base, no prompt changes.
        if denial_code_info:
            prompt += (
                "\nKnown Denial Code Reference (from Atlas' denial "
                "knowledge base):\n"
                f"Code: {denial_code_info['code']}\n"
                f"Category: {denial_code_info['category']}\n"
                f"Description: {denial_code_info['description']}\n"
                f"Typical Recovery Strategy: {denial_code_info['recovery_strategy']}\n"
            )
            if denial_code_info.get("severity"):
                prompt += f"Severity: {denial_code_info['severity']}\n"
            if denial_code_info.get("recoverability"):
                prompt += f"Recoverability: {denial_code_info['recoverability']}\n"
            if denial_code_info.get("typical_recovery_rate") is not None:
                prompt += f"Typical Recovery Rate: {denial_code_info['typical_recovery_rate']}%\n"
            if denial_code_info.get("required_documents"):
                docs = ", ".join(denial_code_info["required_documents"])
                prompt += f"Typically Required Documents: {docs}\n"
            if denial_code_info.get("typical_resolution_days") is not None:
                prompt += (
                    f"Typical Resolution Time: {denial_code_info['typical_resolution_days']} days\n"
                )
            if denial_code_info.get("common_payers"):
                payers = ", ".join(denial_code_info["common_payers"])
                prompt += f"Common Payers: {payers}\n"
            if denial_code_info.get("ai_guidance"):
                prompt += f"Guidance for scoring this case: {denial_code_info['ai_guidance']}\n"
            prompt += (
                "\nUse this reference information to inform your analysis, "
                "but still use your own judgment based on the claim "
                "details above.\n"
            )

        # Richer claim context (payer, diagnoses, procedures, patient age,
        # prior denial history) — all optional, sourced by the caller from
        # relationships already eager-loaded on the claim (see
        # ClaimAnalysisService._build_extra_context). Kept as a separate
        # dict rather than reading claim.payer/claim.patient/etc. directly
        # here so this method still works with any lightweight claim-like
        # object (e.g. in unit tests).
        if extra_context:
            prompt += "\nAdditional Context:\n"
            if extra_context.get("payer_name"):
                prompt += f"Payer: {extra_context['payer_name']}\n"
            if extra_context.get("diagnosis_codes"):
                prompt += f"Diagnosis Codes: {', '.join(extra_context['diagnosis_codes'])}\n"
            if extra_context.get("procedure_codes"):
                prompt += f"Procedure Codes: {', '.join(extra_context['procedure_codes'])}\n"
            if extra_context.get("patient_age") is not None:
                prompt += f"Patient Age: {extra_context['patient_age']}\n"
            if extra_context.get("previous_denials") is not None:
                prompt += (
                    f"Previous Denials for This Patient: {extra_context['previous_denials']}\n"
                )
            if extra_context.get("denial_reason"):
                prompt += f"Denial Reason (raw): {extra_context['denial_reason']}\n"

        return prompt

    def _normalize(self, result: dict) -> dict:
        if not isinstance(result, dict) or "error" in result:
            explanation = (
                result.get("detail", FALLBACK_RESULT["explanation"])
                if isinstance(result, dict)
                else FALLBACK_RESULT["explanation"]
            )
            return dict(FALLBACK_RESULT, explanation=explanation)

        normalized = dict(FALLBACK_RESULT)
        normalized.update({key: result[key] for key in REQUIRED_KEYS if key in result})

        try:
            normalized["confidence"] = max(0.0, min(1.0, float(normalized["confidence"])))
        except (TypeError, ValueError):
            normalized["confidence"] = 0.0

        try:
            normalized["recovery_probability"] = max(
                0.0, min(1.0, float(normalized["recovery_probability"]))
            )
        except (TypeError, ValueError):
            normalized["recovery_probability"] = 0.0

        if not isinstance(normalized["recommended_corrections"], list):
            normalized["recommended_corrections"] = []
        else:
            normalized["recommended_corrections"] = [
                str(item) for item in normalized["recommended_corrections"]
            ]

        normalized["denial_cause"] = str(normalized["denial_cause"])
        normalized["explanation"] = str(normalized["explanation"])

        return normalized


def _is_invalid_raw(result) -> bool:
    """True if the raw AI response can't be trusted as-is: not a dict, an
    explicit error payload, or missing one of the required keys entirely.
    Used to decide whether to retry the AI call before falling back."""
    if not isinstance(result, dict) or "error" in result:
        return True
    return any(key not in result for key in REQUIRED_KEYS)


def _validate_shape(normalized: dict) -> None:
    """
    Best-effort, log-only structural check against ClaimAnalysisAIResponse
    (app/ai/schemas.py). `_normalize()` above already guarantees every
    field is present with a safe/clamped value before this runs, so a
    validation failure here means the schema and the normalization logic
    have drifted apart — worth knowing about, never worth failing the
    request over.
    """
    try:
        ClaimAnalysisAIResponse(**normalized)
    except ValidationError:
        logger.warning("ClaimAnalyzer result failed schema validation: %s", normalized)
