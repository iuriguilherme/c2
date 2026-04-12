import os
from typing import AsyncGenerator
import anthropic as sdk
from agents.protocol import LLMConnectionError


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self._client = sdk.AsyncAnthropic(api_key=self._api_key)

    async def check_available(self) -> bool:
        if not self._api_key:
            return False
        try:
            await self.get_available_models()
            return True
        except Exception:
            return False

    async def get_available_models(self) -> list[str]:
        # Anthropic doesn't expose a public model list endpoint; return known V1 models
        return ["claude-opus-4-5", "claude-sonnet-4-6", "claude-haiku-4-5-20251001"]

    async def generate(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        manifest_json: str,
    ) -> AsyncGenerator[str, None]:
        async with self._client.messages.stream(
            model=model,
            max_tokens=1024,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"{user_prompt}\n\n"
                        f"### CAPABILITIES ###\n{manifest_json}\n### END CAPABILITIES ###"
                    ),
                }
            ],
        ) as stream:
            async for text in stream.text_stream:
                yield text
