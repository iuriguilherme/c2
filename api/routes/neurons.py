from fastapi import APIRouter
from neural.pool import NeuronPool
from neural.models import NeuronDefinition

router = APIRouter(prefix="/neurons", tags=["neurons"])
_pool = NeuronPool.load()


@router.get("/", response_model=list[NeuronDefinition])
async def list_neurons() -> list[NeuronDefinition]:
    return list(_pool.definitions.values())
