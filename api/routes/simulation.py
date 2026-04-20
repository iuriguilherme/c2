from fastapi import APIRouter, Depends, HTTPException
from storage.redis import RedisInteractionStream
from typing import List

router = APIRouter(prefix="/simulation", tags=["simulation"])

_redis_client = None

def set_redis_client(client) -> None:
    global _redis_client
    _redis_client = client

def get_redis():
    if _redis_client is None:
        raise HTTPException(status_code=503, detail="Storage not ready")
    return _redis_client

@router.post("/reset")
async def reset_simulation(redis=Depends(get_redis)) -> dict:
    """Set the simulation command key to 'reset' so the engine process restarts."""
    await redis.set("simulation:command", "reset")
    return {"status": "ok", "message": "Simulation reset requested"}


@router.get("/interactions")
async def get_interactions(
    count: int = 50,
    redis=Depends(get_redis)
) -> List[dict]:
    stream = RedisInteractionStream(redis)
    return await stream.read_recent(count=count)
