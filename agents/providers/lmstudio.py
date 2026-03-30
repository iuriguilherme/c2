from agents.providers.ollama import OllamaProvider


class LMStudioProvider(OllamaProvider):
    """LM Studio uses the same OpenAI-compatible API as Ollama."""
    name = "lmstudio"

    def __init__(self, base_url: str = "http://localhost:1234") -> None:
        super().__init__(base_url=base_url)

    async def get_available_models(self) -> list[str]:
        import httpx
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(f"{self.base_url}/v1/models")
            r.raise_for_status()
            return [m["id"] for m in r.json().get("data", [])]
