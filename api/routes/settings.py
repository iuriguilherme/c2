import json
import logging
import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from storage.redis import RedisLLMLogStream

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["settings"])

_redis_client = None


def set_redis_client(client):
    global _redis_client
    _redis_client = client


_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SETTINGS_FILE = os.path.join(_ROOT, "settings.json")
SETTINGS_EXAMPLE_FILE = os.path.join(_ROOT, "settings.example.json")

class GlobalSettingsModel(BaseModel):
    allowed_providers: list[str]
    default_provider: str

def get_settings_data() -> dict:
    for path in (SETTINGS_FILE, SETTINGS_EXAMPLE_FILE):
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    return json.load(f)
            except Exception as exc:
                logger.warning(
                    "Failed to load settings from %s (%s: %s)",
                    path, type(exc).__name__, exc,
                )
    logger.warning(
        "No settings file found; searched %s and %s",
        SETTINGS_FILE, SETTINGS_EXAMPLE_FILE,
    )
    return {}

@router.get("/")
def get_global_settings():
    """Get global simulation settings."""
    settings = get_settings_data()
    return {
        "available_providers": ["ollama", "openrouter", "lmstudio", "anthropic"],
        "allowed_providers": settings.get("allowed_providers", ["ollama", "openrouter", "lmstudio", "anthropic"]),
        "default_provider": settings.get("default_provider", "ollama")
    }

@router.post("/")
def update_global_settings(settings: GlobalSettingsModel):
    """Update global simulation settings."""
    current = get_settings_data()
    current.update(settings.model_dump())
    try:
        with open(SETTINGS_FILE, "w") as f:
            json.dump(current, f, indent=2)
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to write settings: {e}")


@router.get("/llm-logs")
async def get_llm_logs(count: int = 100):
    if not _redis_client:
        return []
    stream = RedisLLMLogStream(_redis_client)
    return await stream.read_recent(count=count)


@router.delete("/llm-logs/errors")
async def clear_llm_errors():
    if not _redis_client:
        return {"status": "error", "message": "Redis not connected"}
    stream = RedisLLMLogStream(_redis_client)
    await stream.clear_errors()
    return {"status": "ok"}
