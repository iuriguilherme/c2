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

    async def load_many_partial(self, entity_ids: list[str], fields: list[str]) -> list[dict]:
        if not entity_ids:
            return []
        pipe = self._r.pipeline(transaction=False)
        for eid in entity_ids:
            pipe.hmget(f"{self._KEY_PREFIX}:{eid}", *fields)
        results = await pipe.execute()
        entities = []
        for i, res in enumerate(results):
            if res:
                d = {fields[j]: (res[j].decode() if res[j] else None) for j in range(len(fields))}
                if d.get("id") is None:
                    d["id"] = entity_ids[i]
                entities.append(d)
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


class RedisInteractionStream:
    _STREAM_KEY = "interactions:main"

    def __init__(self, redis: Redis) -> None:
        self._r = redis

    async def publish_interaction(
        self,
        event_type: str,
        source_id: str,
        message: str,
        extra_data: dict | None = None,
    ) -> None:
        payload = {
            "type": event_type,
            "source_id": source_id,
            "message": message,
        }
        if extra_data:
            import json
            payload["extra"] = json.dumps(extra_data)

        await self._r.xadd(self._STREAM_KEY, payload, maxlen=1000, approximate=True)

    async def read_recent(self, count: int = 100) -> list[dict]:
        entries = await self._r.xrevrange(self._STREAM_KEY, count=count)
        result = []
        for _id, fields in reversed(entries):
            d = {k.decode(): v.decode() for k, v in fields.items()}
            d["id"] = _id.decode()
            result.append(d)
        return result


class RedisPoolRepository:
    _NEURON_KEY = "pool:neurons"
    _PROFILE_KEY = "pool:profiles"

    def __init__(self, redis: Redis) -> None:
        self._r = redis

    async def get_all_neurons(self) -> dict[str, dict]:
        import json
        data = await self._r.hgetall(self._NEURON_KEY)
        if not data:
            return {}
        return {k.decode(): json.loads(v.decode()) for k, v in data.items()}

    async def save_neuron(self, neuron_type: str, definition: dict) -> None:
        import json
        await self._r.hset(self._NEURON_KEY, neuron_type, json.dumps(definition))

    async def delete_neuron(self, neuron_type: str) -> None:
        await self._r.hdel(self._NEURON_KEY, neuron_type)

    async def get_all_profiles(self) -> dict[str, dict]:
        import json
        data = await self._r.hgetall(self._PROFILE_KEY)
        if not data:
            return {}
        return {k.decode(): json.loads(v.decode()) for k, v in data.items()}

    async def save_profile(self, profile_id: str, profile: dict) -> None:
        import json
        await self._r.hset(self._PROFILE_KEY, profile_id, json.dumps(profile))

    async def delete_profile(self, profile_id: str) -> None:
        await self._r.hdel(self._PROFILE_KEY, profile_id)


class RedisLLMLogStream:
    _SUCCESS_STREAM = "llm_logs:success"
    _ERROR_STREAM = "llm_logs:error"

    def __init__(self, redis: Redis) -> None:
        self._r = redis

    async def publish_log(
        self, provider: str, model: str, success: bool, duration_ms: int, details: str
    ) -> None:
        payload = {
            "provider": provider,
            "model": model,
            "success": str(success),
            "duration_ms": str(duration_ms),
            "details": details,
        }
        if success:
            await self._r.xadd(self._SUCCESS_STREAM, payload, maxlen=100, approximate=True)
        else:
            await self._r.xadd(self._ERROR_STREAM, payload, maxlen=1000, approximate=True)

    async def read_recent(self, count: int = 100) -> list[dict]:
        pipe = self._r.pipeline(transaction=False)
        pipe.xrevrange(self._SUCCESS_STREAM, count=count)
        pipe.xrevrange(self._ERROR_STREAM, count=count)
        results = await pipe.execute()
        
        entries = []
        for _id, fields in results[0] + results[1]:
            d = {k.decode(): v.decode() for k, v in fields.items()}
            d["id"] = _id.decode()
            d["timestamp"] = int(_id.decode().split("-")[0])
            entries.append(d)
        
        entries.sort(key=lambda x: x["timestamp"], reverse=True)
        return entries[:count]

    async def clear_errors(self) -> None:
        await self._r.delete(self._ERROR_STREAM)

