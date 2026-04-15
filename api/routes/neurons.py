from fastapi import APIRouter, Depends, HTTPException
from storage.redis import RedisPoolRepository
from api.routes.entities import get_redis
from neural.models import NeuronDefinition, NeuronProfile

router = APIRouter(prefix="/neurons", tags=["neurons"])


@router.get("/", response_model=list[NeuronDefinition])
async def list_neurons(redis=Depends(get_redis)) -> list[NeuronDefinition]:
    repo = RedisPoolRepository(redis)
    neurons_data = await repo.get_all_neurons()
    return [NeuronDefinition.model_validate(d) for d in neurons_data.values()]

@router.get("/profiles", response_model=list[NeuronProfile])
async def list_neuron_profiles(redis=Depends(get_redis)) -> list[NeuronProfile]:
    repo = RedisPoolRepository(redis)
    profiles_data = await repo.get_all_neuron_profiles()
    return [NeuronProfile.model_validate(d) for d in profiles_data.values()]

@router.get("/profiles/{profile_id}", response_model=NeuronProfile)
async def get_neuron_profile(profile_id: str, redis=Depends(get_redis)) -> NeuronProfile:
    repo = RedisPoolRepository(redis)
    data = await repo.get_neuron_profile(profile_id)
    if not data:
        raise HTTPException(status_code=404, detail="Neuron profile not found")
    return NeuronProfile.model_validate(data)

@router.post("/profiles", response_model=NeuronProfile)
async def create_or_update_neuron_profile(profile: NeuronProfile, redis=Depends(get_redis)) -> NeuronProfile:
    repo = RedisPoolRepository(redis)
    await repo.set_neuron_profile(profile)
    return profile

@router.delete("/profiles/{profile_id}")
async def delete_neuron_profile(profile_id: str, redis=Depends(get_redis)) -> dict:
    repo = RedisPoolRepository(redis)
    await repo.delete_neuron_profile(profile_id)
    return {"status": "ok", "message": "Neuron profile deleted"}
