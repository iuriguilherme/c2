from fastapi import APIRouter, HTTPException, Depends
from neural.models import NeuronDefinition, NeuronType, NeuronProfile
from storage.redis import RedisPoolRepository

router = APIRouter(prefix="/neurons", tags=["neurons"])

_redis_client = None

def set_redis_client(client) -> None:
    global _redis_client
    _redis_client = client

def get_redis():
    if _redis_client is None:
        raise HTTPException(status_code=503, detail="Storage not ready")
    return _redis_client

@router.get("/", response_model=list[NeuronDefinition])
async def list_neurons(redis=Depends(get_redis)) -> list[NeuronDefinition]:
    repo = RedisPoolRepository(redis)
    data = await repo.get_all_neurons()
    return [NeuronDefinition.model_validate(d) for d in data.values()]

@router.get("/profiles", response_model=list[NeuronProfile])
async def list_profiles(redis=Depends(get_redis)) -> list[NeuronProfile]:
    repo = RedisPoolRepository(redis)
    data = await repo.get_all_profiles()
    return [NeuronProfile.model_validate(d) for d in data.values()]

@router.post("/profiles", response_model=NeuronProfile)
async def add_or_update_profile(profile: NeuronProfile, redis=Depends(get_redis)) -> NeuronProfile:
    repo = RedisPoolRepository(redis)
    try:
        if profile.is_default:
            # Unset is_default on others
            data = await repo.get_all_profiles()
            for p_id, p_data in data.items():
                if p_data.get("is_default") and p_id != profile.id:
                    p_data["is_default"] = False
                    await repo.save_profile(p_id, p_data)
                    
        await repo.save_profile(profile.id, profile.model_dump())
        return profile
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save profile: {e}")

@router.delete("/profiles/{profile_id}")
async def delete_profile(profile_id: str, redis=Depends(get_redis)):
    repo = RedisPoolRepository(redis)
    try:
        await repo.delete_profile(profile_id)
        return {"status": "ok", "message": f"Profile {profile_id} deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete profile: {e}")
