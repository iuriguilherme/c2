import json
import os
import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/ollama", tags=["ollama"])

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SETTINGS_FILE = os.path.join(_ROOT, "settings.json")
SETTINGS_EXAMPLE_FILE = os.path.join(_ROOT, "settings.example.json")

class SettingsModel(BaseModel):
    ollama_allowed_models: list[str]
    ollama_default_model: str

class PullModelRequest(BaseModel):
    model: str

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
    return os.environ.get("OLLAMA_BASE_URL", settings.get("ollama_base_url", "http://localhost:11434")).rstrip("/")

def get_api_key() -> str | None:
    return os.environ.get("OLLAMA_API_KEY")

def get_client() -> httpx.AsyncClient:
    headers = {}
    api_key = get_api_key()
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return httpx.AsyncClient(headers=headers, timeout=30.0)


@router.get("/models")
async def list_models():
    """List models downloaded on the Ollama server."""
    base_url = get_base_url()
    try:
        async with get_client() as client:
            r = await client.get(f"{base_url}/api/tags", timeout=5.0)
            if r.status_code != 200:
                raise HTTPException(status_code=r.status_code, detail=r.text)
            return r.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pull")
async def pull_model(req: PullModelRequest):
    """Pull a model from the Ollama registry to the local server."""
    base_url = get_base_url()
    try:
        async with get_client() as client:
            # We don't stream here for simplicity, timeout must be large
            r = await client.post(
                f"{base_url}/api/pull",
                json={"name": req.model, "stream": False},
                timeout=300.0
            )
            if r.status_code != 200:
                raise HTTPException(status_code=r.status_code, detail=r.text)
            return r.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/models/{model_name:path}")
async def delete_model(model_name: str):
    """Delete a model from the Ollama server."""
    base_url = get_base_url()
    try:
        async with get_client() as client:
            r = await client.request(
                "DELETE",
                f"{base_url}/api/delete",
                json={"name": model_name},
                timeout=10.0
            )
            if r.status_code not in (200, 404):
                raise HTTPException(status_code=r.status_code, detail=r.text)
            return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/settings")
def get_settings():
    """Get simulation settings for Ollama."""
    return get_settings_data()


@router.post("/settings")
def update_settings(settings: SettingsModel):
    """Update simulation settings for Ollama."""
    current = get_settings_data()
    # We update current config with what is allowed from SettingsModel
    current.update(settings.model_dump())
    try:
        with open(SETTINGS_FILE, "w") as f:
            json.dump(current, f, indent=2)
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to write settings: {e}")
