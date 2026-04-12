from fastapi import APIRouter, Depends, HTTPException
from storage.redis import RedisEntityRepository

router = APIRouter(prefix="/entities", tags=["entities"])

_redis_client = None


def set_redis_client(client) -> None:
    global _redis_client
    _redis_client = client


def get_redis():
    return _redis_client


@router.get("/archived/{entity_id}")
async def get_archived_entity(entity_id: str, redis=Depends(get_redis)) -> dict:
    repo = RedisEntityRepository(redis)
    data = await repo.load_archive(entity_id)
    if data is None:
        raise HTTPException(status_code=404, detail=f"Archived entity '{entity_id}' not found")
    return data
