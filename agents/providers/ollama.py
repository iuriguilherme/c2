import json
import os
from typing import AsyncGenerator
import httpx
from agents.protocol import LLMConnectionError, LLMTimeoutError


class OllamaProvider:
    name = "ollama"

    def __init__(self, base_url: str = "http://localhost:11434", api_key: str | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or os.environ.get("OLLAMA_API_KEY")

    def _get_client(self, timeout: float) -> httpx.AsyncClient:
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return httpx.AsyncClient(timeout=timeout, headers=headers)

    async def check_available(self) -> bool:
        try:
            async with self._get_client(timeout=5.0) as client:
                r = await client.get(f"{self.base_url}/api/tags")
                return r.status_code == 200
        except Exception:
            return False

    async def get_available_models(self) -> list[str]:
        async with self._get_client(timeout=10.0) as client:
            r = await client.get(f"{self.base_url}/api/tags")
            r.raise_for_status()
            models_on_server = [m["name"] for m in r.json().get("models", [])]

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
                    if "ollama_allowed_models" in settings:
                        allowed_settings = settings["ollama_allowed_models"]
                        if isinstance(allowed_settings, dict):
                            allowed_models = allowed_settings.get("text", [])
                        else:
                            allowed_models = allowed_settings
                except Exception:
                    pass
                break

        if allowed_models is None or not allowed_models:
            return []

        return [m for m in models_on_server if m in allowed_models or m.split(":")[0] in allowed_models]

    async def generate(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        manifest_json: str,
    ) -> AsyncGenerator[str, None]:
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": (
                        f"{user_prompt}\n\n"
                        f"### CAPABILITIES ###\n{manifest_json}\n### END CAPABILITIES ###"
                    ),
                },
            ],
            "stream": True,
        }
        try:
            async with self._get_client(timeout=30.0) as client:
                async with client.stream(
                    "POST", f"{self.base_url}/api/chat", json=payload
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line.strip():
                            continue
                        data = json.loads(line)
                        chunk = data.get("message", {}).get("content", "")
                        if chunk:
                            yield chunk
        except httpx.ConnectError as e:
            raise LLMConnectionError(str(e)) from e
        except httpx.TimeoutException as e:
            raise LLMTimeoutError(str(e)) from e
