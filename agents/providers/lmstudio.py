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
            models_on_server = [m["id"] for m in r.json().get("data", [])]

        import json
        import os
        _root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        settings_path = os.path.join(_root, "settings.json")
        settings_example_path = os.path.join(_root, "settings.example.json")
        allowed_models = None
        for path in (settings_path, settings_example_path):
            if os.path.exists(path):
                try:
                    with open(path, "r") as f:
                        settings = json.load(f)
                    if "lmstudio_allowed_models" in settings:
                        allowed_settings = settings["lmstudio_allowed_models"]
                        if isinstance(allowed_settings, dict):
                            allowed_models = allowed_settings.get("text", [])
                        else:
                            allowed_models = allowed_settings
                except Exception:
                    pass
                break

        if allowed_models is None or not allowed_models:
            return []

        return [m for m in models_on_server if m in allowed_models]
