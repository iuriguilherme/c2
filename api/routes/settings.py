import json
import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/settings", tags=["settings"])

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SETTINGS_FILE = os.path.join(_ROOT, "settings.json")
SETTINGS_EXAMPLE_FILE = os.path.join(_ROOT, "settings.example.json")

class GlobalSettingsModel(BaseModel):
    allowed_providers: list[str]

def get_settings_data() -> dict:
    for path in (SETTINGS_FILE, SETTINGS_EXAMPLE_FILE):
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    return json.load(f)
            except Exception:
                pass
    return {}

@router.get("/")
def get_global_settings():
    """Get global simulation settings."""
    settings = get_settings_data()
    return {"allowed_providers": settings.get("allowed_providers", ["ollama", "openrouter", "lmstudio", "anthropic"])}

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
