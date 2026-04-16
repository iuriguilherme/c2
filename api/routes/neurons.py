from fastapi import APIRouter, HTTPException
from neural.pool import NeuronPool, _DATA_PATH
from neural.models import NeuronDefinition, NeuronType
import json

router = APIRouter(prefix="/neurons", tags=["neurons"])
_pool = NeuronPool.load()


def save_pool(pool: NeuronPool):
    """Save the current pool definitions back to the JSON file."""
    data = [defn.model_dump() for defn in pool.definitions.values()]
    with open(_DATA_PATH, "w") as f:
        json.dump(data, f, indent=2)


@router.get("/", response_model=list[NeuronDefinition])
async def list_neurons() -> list[NeuronDefinition]:
    return list(_pool.definitions.values())


@router.post("/", response_model=NeuronDefinition)
async def add_or_update_neuron(neuron: NeuronDefinition) -> NeuronDefinition:
    """Add a new neuron definition or update an existing one."""
    _pool.definitions[neuron.neuron_type] = neuron
    try:
        save_pool(_pool)
        return neuron
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save neuron pool: {e}")


@router.delete("/{neuron_type}")
async def delete_neuron(neuron_type: NeuronType):
    """Delete a neuron definition from the pool."""
    if neuron_type not in _pool.definitions:
        raise HTTPException(status_code=404, detail="Neuron type not found")
    
    del _pool.definitions[neuron_type]
    try:
        save_pool(_pool)
        return {"status": "ok", "message": f"Neuron {neuron_type} deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save neuron pool: {e}")
