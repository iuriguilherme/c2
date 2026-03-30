import random
from dataclasses import dataclass
from agents.protocol import LLMProvider


@dataclass
class ModelAssignment:
    provider_name: str
    model: str


class ModelPool:
    """Discovers available models at startup, assigns randomly to new entities."""

    def __init__(self) -> None:
        self._pool: list[tuple[LLMProvider, str]] = []

    async def discover(self, providers: list[LLMProvider]) -> None:
        self._pool.clear()
        for provider in providers:
            if await provider.check_available():
                models = await provider.get_available_models()
                for model in models:
                    self._pool.append((provider, model))

    def assign_random(self, rng: random.Random | None = None) -> ModelAssignment:
        if not self._pool:
            raise RuntimeError("No models available in pool")
        r = rng or random.Random()
        provider, model = r.choice(self._pool)
        return ModelAssignment(provider_name=provider.name, model=model)

    def get_provider(self, provider_name: str) -> LLMProvider | None:
        for provider, _ in self._pool:
            if provider.name == provider_name:
                return provider
        return None

    @property
    def size(self) -> int:
        return len(self._pool)
