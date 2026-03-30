from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/entities", tags=["entities"])


@router.get("/archived/{entity_id}")
async def get_archived_entity(entity_id: str) -> dict:
    raise HTTPException(status_code=501, detail="Requires Redis connection")
