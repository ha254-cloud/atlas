"""
AI-layer exceptions.

Every AI feature (claim analysis, appeal generation, document summaries,
anything built on the gateway later) should only ever have to catch
`AIProviderError` — never an SDK-specific exception type like
`openai.OpenAIError`. Providers translate their own SDK errors into this
at the point they occur; the gateway also wraps anything a provider might
have missed, so it's the single exception type the rest of the codebase
needs to know about.
"""


class AIProviderError(Exception):
    """Raised when an AI provider call fails or returns an invalid response.

    Keeps provider-specific exception types (OpenAI, Anthropic, etc.) from
    leaking into callers outside app/ai/ — callers only need to catch this
    one type regardless of which provider actually served the request.
    """

    def __init__(
        self,
        message: str,
        *,
        task: str | None = None,
        provider: str | None = None,
    ):
        super().__init__(message)
        self.task = task
        self.provider = provider
