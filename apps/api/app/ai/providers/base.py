from abc import ABC, abstractmethod


class AIProvider(ABC):
    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system: str | None = None,
        *,
        task: str | None = None,
        model: str | None = None,
        prompt_version: str | None = None,
    ) -> str:
        """
        Generate text from the configured AI model.

        `task`/`model`/`prompt_version` are optional attribution/override
        hints supplied by the AI Gateway (task name for cost-log grouping,
        model override for per-task model selection, prompt version for
        the cost/usage audit trail) — implementations that don't need
        them (the provider stubs) can simply ignore them.
        """
        raise NotImplementedError
