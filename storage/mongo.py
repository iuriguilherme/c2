import os
import json
import logging
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import Document, init_beanie
from typing import Optional

logger = logging.getLogger(__name__)

class SystemPrompt(Document):
    name: str
    content: str
    is_default: bool = False

    class Settings:
        name = "system_prompts"

async def init_mongo() -> None:
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    settings_path = os.path.join(_root, "settings.json")
    example_path = os.path.join(_root, "settings.example.json")

    mongo_url = "mongodb://localhost:27017"
    for path in (settings_path, example_path):
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    settings = json.load(f)
                    mongo_url = settings.get("mongo_url", mongo_url)
                break
            except Exception:
                pass

    mongo_url = os.environ.get("MONGO_URL", mongo_url)

    client = AsyncIOMotorClient(mongo_url)
    await init_beanie(database=client["agi_simulation"], document_models=[SystemPrompt])

    count = await SystemPrompt.find_all().count()
    if count == 0:
        logger.info("Initializing default system prompts...")
        from simulation.factory import _PERSONALITY_TEMPLATES
        prompts = [
            SystemPrompt(
                name=f"Personality {i+1}",
                content=template,
                is_default=True
            ) for i, template in enumerate(_PERSONALITY_TEMPLATES)
        ]
        await SystemPrompt.insert_many(prompts)
