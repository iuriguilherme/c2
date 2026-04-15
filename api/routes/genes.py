from fastapi import APIRouter, HTTPException, Depends
from storage.redis import RedisPoolRepository
from api.routes.entities import get_redis
from genetics.models import GeneDefinition, GeneType

router = APIRouter(prefix="/genes", tags=["genes"])

@router.get("/", response_model=list[GeneDefinition])
async def list_genes(redis=Depends(get_redis)) -> list[GeneDefinition]:
    repo = RedisPoolRepository(redis)
    genes_data = await repo.get_all_genes()
    return [GeneDefinition.model_validate(d) for d in genes_data.values()]


@router.get("/{gene_type}", response_model=GeneDefinition)
async def get_gene(gene_type: str, redis=Depends(get_redis)) -> GeneDefinition:
    try:
        gt = GeneType(gene_type)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Gene type '{gene_type}' not found")

    repo = RedisPoolRepository(redis)
    genes_data = await repo.get_all_genes()
    defn_data = genes_data.get(gt.value)
    if not defn_data:
        raise HTTPException(status_code=404, detail=f"Gene type '{gene_type}' not found")
    return GeneDefinition.model_validate(defn_data)
