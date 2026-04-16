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

    async def discover(self, providers: list[LLMProvider], settings: dict = None) -> None:
        """
        Populate the pool based strictly on settings:
        For each allowed provider, randomly select among its allowed models.
        If no allowed models, use its default model.
        """
        self._pool.clear()
        if not settings:
            settings = {}

        allowed_providers = settings.get("allowed_providers", ["ollama", "openrouter", "lmstudio", "anthropic"])

        for provider in providers:
            if provider.name not in allowed_providers:
                continue

            allowed_models = settings.get(f"{provider.name}_allowed_models", {})
            if isinstance(allowed_models, dict):
                allowed_models = allowed_models.get("text", [])

            if allowed_models:
                for model in allowed_models:
                    self._pool.append((provider, model))
            else:
                default_model = settings.get(f"{provider.name}_default_model", {})
                if isinstance(default_model, dict):
                    default_model = default_model.get("text", "")
                if default_model:
                    self._pool.append((provider, default_model))

    def assign_random(self, rng: random.Random | None = None) -> ModelAssignment:
        if not self._pool:
            raise RuntimeError("No models configured in settings. Please configure allowed models or a default model for at least one allowed provider.")
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
