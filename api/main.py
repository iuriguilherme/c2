from fastapi import FastAPI
from api.routes.genes import router as genes_router
from api.routes.neurons import router as neurons_router
from api.routes.entities import router as entities_router

app = FastAPI(title="AGI Simulation API", version="1.0.0")

app.include_router(genes_router)
app.include_router(neurons_router)
app.include_router(entities_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
