from app.ai.providers.base import AIProvider


class GeminiProvider(AIProvider):
    async def generate(
        self,
        prompt: str,
        system: str | None = None,
        *,
        task: str | None = None,
        model: str | None = None,
        prompt_version: str | None = None,
    ) -> str:
        # TODO: implement Gemini SDK integration
        return f"[Gemini] Generated response for prompt: {prompt[:100]}..."
