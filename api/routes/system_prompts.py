from fastapi import APIRouter, HTTPException
from storage.mongo import SystemPrompt
from pydantic import BaseModel
from typing import List

router = APIRouter(prefix="/system-prompts", tags=["system-prompts"])

class SystemPromptCreate(BaseModel):
    name: str
    content: str
    is_default: bool = False

class SystemPromptUpdate(BaseModel):
    name: str | None = None
    content: str | None = None
    is_default: bool | None = None

@router.get("/", response_model=List[dict])
async def get_system_prompts():
    prompts = await SystemPrompt.find_all().to_list()
    return [{"id": str(p.id), "name": p.name, "content": p.content, "is_default": p.is_default} for p in prompts]

@router.post("/", response_model=dict)
async def create_system_prompt(prompt: SystemPromptCreate):
    new_prompt = SystemPrompt(name=prompt.name, content=prompt.content, is_default=prompt.is_default)
    await new_prompt.insert()
    return {"id": str(new_prompt.id), "name": new_prompt.name, "content": new_prompt.content, "is_default": new_prompt.is_default}

@router.patch("/{prompt_id}", response_model=dict)
async def update_system_prompt(prompt_id: str, updates: SystemPromptUpdate):
    from bson import ObjectId
    try:
        oid = ObjectId(prompt_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID format")

    prompt = await SystemPrompt.get(oid)
    if not prompt:
        raise HTTPException(status_code=404, detail="System prompt not found")

    if updates.name is not None:
        prompt.name = updates.name
    if updates.content is not None:
        prompt.content = updates.content
    if updates.is_default is not None:
        prompt.is_default = updates.is_default

    await prompt.save()
    return {"id": str(prompt.id), "name": prompt.name, "content": prompt.content, "is_default": prompt.is_default}

@router.delete("/{prompt_id}")
async def delete_system_prompt(prompt_id: str):
    from bson import ObjectId
    try:
        oid = ObjectId(prompt_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID format")

    prompt = await SystemPrompt.get(oid)
    if not prompt:
        raise HTTPException(status_code=404, detail="System prompt not found")

    await prompt.delete()
    return {"status": "ok"}
