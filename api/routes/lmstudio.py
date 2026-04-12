import json
import os
import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/lmstudio", tags=["lmstudio"])

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SETTINGS_FILE = os.path.join(_ROOT, "settings.json")
SETTINGS_EXAMPLE_FILE = os.path.join(_ROOT, "settings.example.json")

class SettingsModel(BaseModel):
    lmstudio_allowed_models: list[str]
    lmstudio_default_model: str

def get_settings_data() -> dict:
    for path in (SETTINGS_FILE, SETTINGS_EXAMPLE_FILE):
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    return json.load(f)
            except Exception:
                pass
    return {}

def get_base_url() -> str:
    settings = get_settings_data()
    return os.environ.get("LMSTUDIO_BASE_URL", settings.get("lmstudio_base_url", "http://localhost:1234")).rstrip("/")

def get_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=30.0)

@router.get("/models")
async def list_models():
    """List available models from LM Studio."""
    base_url = get_base_url()
    try:
        async with get_client() as client:
            r = await client.get(f"{base_url}/v1/models", timeout=5.0)
            if r.status_code != 200:
                raise HTTPException(status_code=r.status_code, detail=r.text)
            return r.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/settings")
def get_settings():
    """Get simulation settings for LM Studio."""
    settings = get_settings_data()
    return {
        "lmstudio_allowed_models": settings.get("lmstudio_allowed_models", []),
        "lmstudio_default_model": settings.get("lmstudio_default_model", "")
    }

@router.post("/settings")
def update_settings(settings: SettingsModel):
    """Update simulation settings for LM Studio."""
    current = get_settings_data()
    current.update(settings.model_dump())
    try:
        with open(SETTINGS_FILE, "w") as f:
            json.dump(current, f, indent=2)
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to write settings: {e}")
