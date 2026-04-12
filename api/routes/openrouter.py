import json
import os
import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/openrouter", tags=["openrouter"])

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SETTINGS_FILE = os.path.join(_ROOT, "settings.json")
SETTINGS_EXAMPLE_FILE = os.path.join(_ROOT, "settings.example.json")

class SettingsModel(BaseModel):
    openrouter_allowed_models: dict[str, list[str]]
    openrouter_default_model: dict[str, str]

def get_settings_data() -> dict:
    for path in (SETTINGS_FILE, SETTINGS_EXAMPLE_FILE):
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    return json.load(f)
            except Exception:
                pass
    return {}

def get_api_key() -> str | None:
    return os.environ.get("OPENROUTER_API_KEY")

def get_client() -> httpx.AsyncClient:
    headers = {}
    api_key = get_api_key()
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    # OpenRouter requires HTTP referer or X-Title for ranking sometimes, but we skip for now.
    return httpx.AsyncClient(headers=headers, timeout=30.0)

@router.get("/models")
async def list_models():
    """List available models from OpenRouter."""
    try:
        async with get_client() as client:
            r = await client.get("https://openrouter.ai/api/v1/models", timeout=10.0)
            if r.status_code != 200:
                raise HTTPException(status_code=r.status_code, detail=r.text)
            return r.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/settings")
def get_settings():
    """Get simulation settings for OpenRouter."""
    settings = get_settings_data()
    return {
        "openrouter_allowed_models": settings.get("openrouter_allowed_models", {}),
        "openrouter_default_model": settings.get("openrouter_default_model", {})
    }

@router.post("/settings")
def update_settings(settings: SettingsModel):
    """Update simulation settings for OpenRouter."""
    current = get_settings_data()
    current.update(settings.model_dump())
    try:
        with open(SETTINGS_FILE, "w") as f:
            json.dump(current, f, indent=2)
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to write settings: {e}")
