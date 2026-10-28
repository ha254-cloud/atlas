from app.ai.providers.openai import OpenAIProvider


class AIEngine:
    """
    Legacy entry point — delegates to the AI Gateway.
    Retained for backward compatibility with existing callers.
    New code should use `app.ai.gateway.gateway` directly.
    """

    def __init__(self):
        self.provider = OpenAIProvider()

    async def generate(
        self,
        prompt: str,
        system: str | None = None,
    ) -> str:
        return await self.provider.generate(
            prompt=prompt,
            system=system,
        )

    async def generate_json(
        self,
        prompt: str,
        system: str | None = None,
    ) -> dict:
        return await self.provider.generate_json(
            prompt=prompt,
            system=system,
        )
