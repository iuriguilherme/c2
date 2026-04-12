from fastapi import APIRouter, Depends, HTTPException, Path
from storage.redis import RedisEntityRepository

router = APIRouter(prefix="/entities", tags=["entities"])

_redis_client = None


def set_redis_client(client) -> None:
    global _redis_client
    _redis_client = client


def get_redis():
    if _redis_client is None:
        raise HTTPException(status_code=503, detail="Storage not ready")
    return _redis_client


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
