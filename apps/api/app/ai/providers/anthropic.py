from app.ai.providers.base import AIProvider


class AnthropicProvider(AIProvider):
    async def generate(
        self,
        prompt: str,
        system: str | None = None,
        *,
        task: str | None = None,
        model: str | None = None,
        prompt_version: str | None = None,
    ) -> str:
        # TODO: implement Anthropic SDK integration
        return f"[Anthropic] Generated response for prompt: {prompt[:100]}..."
