from typing import AsyncGenerator, Protocol, runtime_checkable


class LLMError(Exception):
    pass


class LLMTimeoutError(LLMError):
    pass


class LLMConnectionError(LLMError):
    pass


class LLMRateLimitError(LLMError):
    def __init__(self, message: str, retry_after: int = 60) -> None:
        super().__init__(message)
        self.retry_after = retry_after


@runtime_checkable
class LLMProvider(Protocol):
    name: str

    async def generate(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        manifest_json: str,
    ) -> AsyncGenerator[str, None]: ...

    async def check_available(self) -> bool: ...

    async def get_available_models(self) -> list[str]: ...
