from fastapi import APIRouter, Depends, HTTPException, Path
from storage.redis import RedisEntityRepository
from pydantic import BaseModel
from typing import Optional
from simulation.randomness import generate_random_seed, get_random_float
from genetics.models import GeneType, GeneInstance

router = APIRouter(prefix="/entities", tags=["entities"])

_redis_client = None


def set_redis_client(client) -> None:
    global _redis_client
    _redis_client = client


def get_redis():
    if _redis_client is None:
        raise HTTPException(status_code=503, detail="Storage not ready")
    return _redis_client


class EntityAddRequest(BaseModel):
    brain_size: Optional[float] = None
    lifespan: Optional[float] = None
    think_interval: Optional[float] = None
    reproduction_threshold: Optional[float] = None
    neuron_affinity: Optional[float] = None


@router.post("/")
async def add_entity(
    req: EntityAddRequest,
    redis=Depends(get_redis)
):
    import time
    from genetics import GenePool
    from neural.pool import NeuronPool
    from agents.pool import ModelPool
    from agents.providers.ollama import OllamaProvider
    from agents.providers.openrouter import OpenRouterProvider
    from agents.providers.anthropic import AnthropicProvider
    from agents.providers.lmstudio import LMStudioProvider
    from simulation.factory import EntityFactory
    import random
    import os
    import json

    repo = RedisEntityRepository(redis)
    gene_pool = GenePool.load()
    neuron_pool = NeuronPool.load()
    factory = EntityFactory(gene_pool=gene_pool, neuron_pool=neuron_pool)

    # Re-use pool setup logic
    _root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    settings = {}
    for settings_path in (
        os.path.join(_root, "settings.json"),
        os.path.join(_root, "settings.example.json"),
    ):
        if os.path.exists(settings_path):
            try:
                with open(settings_path, "r") as f:
                    settings = json.load(f)
                break
            except Exception:
                pass
    allowed_providers = settings.get("allowed_providers", ["ollama", "openrouter", "lmstudio", "anthropic"])
    all_providers = [
        OllamaProvider(base_url=settings.get("ollama_base_url", "http://localhost:11434")),
        OpenRouterProvider(),
        LMStudioProvider(base_url=settings.get("lmstudio_base_url", "http://localhost:1234")),
        AnthropicProvider(),
    ]
    providers = [p for p in all_providers if p.name in allowed_providers]
    model_pool = ModelPool()
    await model_pool.discover(providers)

    if model_pool.size == 0:
        p = next(p for p in all_providers if p.name == "ollama")
        model_pool._pool.append((p, "llama3.2"))

    seed = generate_random_seed()
    r = random.Random(seed)

    genome = gene_pool.default_genome()
    # Apply overrides
    if req.brain_size is not None:
        genome.genes[GeneType.BRAIN_SIZE] = GeneInstance(gene_type=GeneType.BRAIN_SIZE, value=req.brain_size)
    if req.lifespan is not None:
        genome.genes[GeneType.LIFESPAN] = GeneInstance(gene_type=GeneType.LIFESPAN, value=req.lifespan)
    if req.think_interval is not None:
        genome.genes[GeneType.THINK_INTERVAL] = GeneInstance(gene_type=GeneType.THINK_INTERVAL, value=req.think_interval)
    if req.reproduction_threshold is not None:
        genome.genes[GeneType.REPRODUCTION_THRESHOLD] = GeneInstance(gene_type=GeneType.REPRODUCTION_THRESHOLD, value=req.reproduction_threshold)
    if req.neuron_affinity is not None:
        genome.genes[GeneType.NEURON_AFFINITY] = GeneInstance(gene_type=GeneType.NEURON_AFFINITY, value=req.neuron_affinity)

    assignment = model_pool.assign_random(rng=r)
    entity_id = f"entity-manual-{int(time.time())}-{r.randint(1000, 9999)}"

    entity = factory.create(
        entity_id=entity_id,
        genome=genome,
        model_assignment=assignment,
        rng=r,
    )

    void_w = float(os.environ.get("VOID_WIDTH", settings.get("void_width", 1000.0)))
    void_h = float(os.environ.get("VOID_HEIGHT", settings.get("void_height", 1000.0)))
    entity.position_x = get_random_float(0, void_w)
    entity.position_y = get_random_float(0, void_h)

    await repo.save(entity.id, entity.to_storage_dict())

    return {
        "status": "ok",
        "entity_id": entity.id,
        "model": entity.model,
        "provider": entity.provider_name
    }


@router.get("/{entity_id}")
async def get_entity(
    entity_id: str = Path(..., pattern=r"^[\w-]{1,128}$"),
    redis=Depends(get_redis),
) -> dict:
    repo = RedisEntityRepository(redis)
    data = await repo.load(entity_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Entity not found")
    return data


@router.get("/archived/{entity_id}")
async def get_archived_entity(
    entity_id: str = Path(..., pattern=r"^[\w-]{1,128}$"),
    redis=Depends(get_redis),
) -> dict:
    repo = RedisEntityRepository(redis)
    data = await repo.load_archive(entity_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Archived entity not found")
    return data
