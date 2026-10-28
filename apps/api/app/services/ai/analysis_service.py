import logging
import time

from pydantic import ValidationError

from app.ai.gateway import AIGateway
from app.ai.gateway import gateway as default_gateway
from app.models.claim import Claim
from app.schemas.claim_analysis import ClaimAnalysisResult
from app.services.ai.context_builder import ClaimContextBuilder
from app.services.ai.prompts.claim_analysis import (
    PROMPT_VERSION,
    build_claim_analysis_prompt,
)

logger = logging.getLogger(__name__)

TASK_NAME = "claim_analysis"
MAX_ATTEMPTS = 2


class AIAnalysisService:
    """Orchestrate claim analysis without persistence or task concerns."""

    def __init__(
        self,
        ai_gateway: AIGateway | None = None,
        context_builder: ClaimContextBuilder | None = None,
    ) -> None:
        self.gateway = ai_gateway or default_gateway
        self.context_builder = context_builder or ClaimContextBuilder()

    @property
    def model(self) -> str:
        return self.gateway.model_for(TASK_NAME)

    @property
    def prompt_version(self) -> str:
        return PROMPT_VERSION

    async def analyze(self, claim: Claim) -> ClaimAnalysisResult:
        context = self.context_builder.build(claim)
        messages = build_claim_analysis_prompt(context)
        system_prompt = messages[0]["content"]
        user_prompt = messages[1]["content"]
        claim_id = getattr(claim, "id", None)
        model = self.model

        for attempt in range(1, MAX_ATTEMPTS + 1):
            started_at = time.monotonic()
            try:
                raw_result = await self.gateway.generate_json(
                    task=TASK_NAME,
                    prompt=user_prompt,
                    system=system_prompt,
                )
            except Exception:
                latency_ms = int((time.monotonic() - started_at) * 1000)
                logger.error(
                    "AI claim analysis gateway call failed "
                    "claim_id=%s model=%s latency_ms=%s attempt=%s status=error",
                    claim_id,
                    model,
                    latency_ms,
                    attempt,
                )
                raise
            latency_ms = int((time.monotonic() - started_at) * 1000)

            try:
                result = ClaimAnalysisResult.model_validate(raw_result)
            except ValidationError:
                logger.warning(
                    "AI claim analysis validation failed "
                    "claim_id=%s model=%s latency_ms=%s attempt=%s status=invalid",
                    claim_id,
                    model,
                    latency_ms,
                    attempt,
                )
                if attempt == MAX_ATTEMPTS:
                    raise
                continue

            logger.info(
                "AI claim analysis completed "
                "claim_id=%s model=%s latency_ms=%s attempt=%s status=success",
                claim_id,
                model,
                latency_ms,
                attempt,
            )
            return result

        raise RuntimeError("AI claim analysis exhausted attempts without a result")
