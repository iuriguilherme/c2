import json
import httpx
from typing import AsyncGenerator
from agents.providers.ollama import OllamaProvider
from agents.protocol import LLMConnectionError, LLMTimeoutError


class LMStudioProvider(OllamaProvider):
    """LM Studio uses the OpenAI-compatible API."""
    name = "lmstudio"

    def __init__(self, base_url: str = "http://localhost:1234") -> None:
        super().__init__(base_url=base_url)

    async def check_available(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(f"{self.base_url}/v1/models")
                return r.status_code == 200
        except Exception:
            return False

    async def get_available_models(self) -> list[str]:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.get(f"{self.base_url}/v1/models")
                r.raise_for_status()
                return [m["id"] for m in r.json().get("data", [])]
        except httpx.ConnectError as e:
            raise LLMConnectionError(str(e)) from e
        except httpx.TimeoutException as e:
            raise LLMTimeoutError(str(e)) from e

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
            async with httpx.AsyncClient(timeout=30.0) as client:
                async with client.stream(
                    "POST", f"{self.base_url}/v1/chat/completions", json=payload
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line.startswith("data: "):
                            continue

                        data_str = line[len("data: "):].strip()
                        if data_str == "[DONE]":
                            break

                        try:
                            data = json.loads(data_str)
                            choices = data.get("choices", [])
                            if not choices:
                                continue
                            chunk = choices[0].get("delta", {}).get("content", "")
                            if chunk:
                                yield chunk
                        except json.JSONDecodeError:
                            continue
        except httpx.ConnectError as e:
            raise LLMConnectionError(str(e)) from e
        except httpx.TimeoutException as e:
            raise LLMTimeoutError(str(e)) from e
