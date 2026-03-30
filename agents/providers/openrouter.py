import os
from typing import AsyncGenerator
from openai import AsyncOpenAI
from agents.protocol import LLMConnectionError, LLMRateLimitError


class OpenRouterProvider:
    name = "openrouter"

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or os.environ.get("OPENROUTER_API_KEY", "")
        self._client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=self._api_key,
        )

    async def check_available(self) -> bool:
        if not self._api_key:
            return False
        try:
            models = await self.get_available_models()
            return len(models) > 0
        except Exception:
            return False

    async def get_available_models(self) -> list[str]:
        response = await self._client.models.list()
        return [m.id for m in response.data]

    async def generate(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        manifest_json: str,
    ) -> AsyncGenerator[str, None]:
        stream = await self._client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": (
                        f"{user_prompt}\n\n"
                        f"### CAPABILITIES ###\n{manifest_json}\n### END CAPABILITIES ###"
                    ),
                },
            ],
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta
