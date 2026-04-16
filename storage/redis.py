from redis.asyncio import Redis


class RedisEntityRepository:
    _KEY_PREFIX = "entity"
    _ARCHIVE_PREFIX = "archive"
    _LIVING_SET = "living_entities"

    def __init__(self, redis: Redis) -> None:
        self._r = redis

    async def save(self, entity_id: str, data: dict) -> None:
        key = f"{self._KEY_PREFIX}:{entity_id}"
        await self._r.hset(key, mapping={k: str(v) for k, v in data.items()})
        if str(data.get("alive", "True")) in ("True", "1", "true"):
            await self._r.sadd(self._LIVING_SET, entity_id)
        else:
            await self._r.srem(self._LIVING_SET, entity_id)

    async def load(self, entity_id: str) -> dict | None:
        key = f"{self._KEY_PREFIX}:{entity_id}"
        data = await self._r.hgetall(key)
        if not data:
            return None
        return {k.decode(): v.decode() for k, v in data.items()}

    async def list_living(self) -> list[str]:
        members = await self._r.smembers(self._LIVING_SET)
        return [m.decode() for m in members]

    async def load_many(self, entity_ids: list[str]) -> list[dict]:
        if not entity_ids:
            return []
        pipe = self._r.pipeline(transaction=False)
        for eid in entity_ids:
            pipe.hgetall(f"{self._KEY_PREFIX}:{eid}")
        results = await pipe.execute()
        entities = []
        for res in results:
            if res:
                entities.append({k.decode(): v.decode() for k, v in res.items()})
        return entities

    async def archive(self, entity_id: str) -> None:
        data = await self.load(entity_id)
        if data:
            archive_key = f"{self._ARCHIVE_PREFIX}:{entity_id}"
            await self._r.hset(archive_key, mapping=data)
        await self._r.delete(f"{self._KEY_PREFIX}:{entity_id}")
        await self._r.srem(self._LIVING_SET, entity_id)

    async def load_archive(self, entity_id: str) -> dict | None:
        key = f"{self._ARCHIVE_PREFIX}:{entity_id}"
        data = await self._r.hgetall(key)
        if not data:
            return None
        return {k.decode(): v.decode() for k, v in data.items()}


import json
from genetics.models import GeneDefinition, GeneType
from neural.models import NeuronDefinition, NeuronType, NeuronProfile

class RedisPoolRepository:
    _GENE_KEY = "pool:genes"
    _NEURON_KEY = "pool:neurons"
    _NEURON_PROFILES_KEY = "pool:neuron_profiles"

    def __init__(self, redis: Redis) -> None:
        self._r = redis

    async def get_all_genes(self) -> dict[str, dict]:
        data = await self._r.hgetall(self._GENE_KEY)
        return {k.decode(): json.loads(v.decode()) for k, v in data.items()}

    async def set_gene(self, gene: GeneDefinition) -> None:
        await self._r.hset(self._GENE_KEY, gene.gene_type.value, gene.model_dump_json())

    async def get_all_neurons(self) -> dict[str, dict]:
        data = await self._r.hgetall(self._NEURON_KEY)
        return {k.decode(): json.loads(v.decode()) for k, v in data.items()}

    async def set_neuron(self, neuron: NeuronDefinition) -> None:
        await self._r.hset(self._NEURON_KEY, neuron.neuron_type.value, neuron.model_dump_json())

    async def get_all_neuron_profiles(self) -> dict[str, dict]:
        data = await self._r.hgetall(self._NEURON_PROFILES_KEY)
        return {k.decode(): json.loads(v.decode()) for k, v in data.items()}

    async def get_neuron_profile(self, profile_id: str) -> dict | None:
        data = await self._r.hget(self._NEURON_PROFILES_KEY, profile_id)
        if not data:
            return None
        return json.loads(data.decode())

    async def set_neuron_profile(self, profile: NeuronProfile) -> None:
        await self._r.hset(self._NEURON_PROFILES_KEY, profile.id, profile.model_dump_json())

    async def delete_neuron_profile(self, profile_id: str) -> None:
        await self._r.hdel(self._NEURON_PROFILES_KEY, profile_id)


class RedisTickStream:
    _STREAM_KEY = "ticks:main"

    def __init__(self, redis: Redis) -> None:
        self._r = redis

    async def publish_tick(self, tick: int, entity_count: int) -> None:
        await self._r.xadd(
            self._STREAM_KEY,
            {"tick": str(tick), "entity_count": str(entity_count)},
        )

    async def read_recent(self, count: int = 100) -> list[dict]:
        entries = await self._r.xrevrange(self._STREAM_KEY, count=count)
        result = []
        for _id, fields in reversed(entries):
            result.append({k.decode(): v.decode() for k, v in fields.items()})
        return result
