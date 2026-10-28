import logging
import time

from pydantic import ValidationError

from app.ai.gateway import AIGateway
from app.ai.gateway import gateway as default_gateway
from app.appeals.schemas import AppealResult
from app.models.claim import Claim
from app.services.ai.appeal_context_builder import AppealContextBuilder
from app.services.ai.prompts.appeal_generation import (
    PROMPT_VERSION,
    build_appeal_generation_prompt,
)

logger = logging.getLogger(__name__)

TASK_NAME = "appeal"
MAX_ATTEMPTS = 2


class AppealGenerationService:
    """Generate and validate an appeal without persistence or task concerns."""

    def __init__(
        self,
        ai_gateway: AIGateway | None = None,
        context_builder: AppealContextBuilder | None = None,
    ) -> None:
        self.gateway = ai_gateway or default_gateway
        self.context_builder = context_builder or AppealContextBuilder()

    @property
    def model(self) -> str:
        return self.gateway.model_for(TASK_NAME)

    @property
    def prompt_version(self) -> str:
        return PROMPT_VERSION

    async def generate(self, claim: Claim) -> AppealResult:
        context = self.context_builder.build(claim)
        messages = build_appeal_generation_prompt(context)
        system_prompt = messages[0]["content"]
        user_prompt = messages[1]["content"]

        for attempt in range(1, MAX_ATTEMPTS + 1):
            started_at = time.monotonic()
            try:
                raw_result = await self.gateway.generate_json(
                    task=TASK_NAME,
                    prompt=user_prompt,
                    system=system_prompt,
                )
            except Exception:
                logger.error(
                    "AI appeal gateway call failed "
                    "claim_id=%s model=%s latency_ms=%s attempt=%s status=error",
                    claim.id,
                    self.model,
                    int((time.monotonic() - started_at) * 1000),
                    attempt,
                )
                raise

            latency_ms = int((time.monotonic() - started_at) * 1000)
            try:
                result = AppealResult.model_validate(raw_result)
            except ValidationError:
                logger.warning(
                    "AI appeal validation failed "
                    "claim_id=%s model=%s latency_ms=%s attempt=%s status=invalid",
                    claim.id,
                    self.model,
                    latency_ms,
                    attempt,
                )
                if attempt == MAX_ATTEMPTS:
                    raise
                continue

            logger.info(
                "AI appeal generated claim_id=%s model=%s latency_ms=%s attempt=%s status=success",
                claim.id,
                self.model,
                latency_ms,
                attempt,
            )
            return result

        raise RuntimeError("AI appeal generation exhausted attempts without a result")
