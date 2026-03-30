from fastapi import APIRouter, HTTPException
from genetics.pool import GenePool
from genetics.models import GeneDefinition, GeneType

router = APIRouter(prefix="/genes", tags=["genes"])
_pool = GenePool.load()


@router.get("/", response_model=list[GeneDefinition])
async def list_genes() -> list[GeneDefinition]:
    return list(_pool.definitions.values())


@router.get("/{gene_type}", response_model=GeneDefinition)
async def get_gene(gene_type: str) -> GeneDefinition:
    try:
        gt = GeneType(gene_type)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Gene type '{gene_type}' not found")
    defn = _pool.definitions.get(gt)
    if not defn:
        raise HTTPException(status_code=404, detail=f"Gene type '{gene_type}' not found")
    return defn
