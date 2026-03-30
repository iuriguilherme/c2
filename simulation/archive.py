from storage.redis import RedisEntityRepository


class EntityArchive:
    def __init__(self, repo: RedisEntityRepository) -> None:
        self._repo = repo

    async def archive(self, entity_id: str) -> None:
        """Synchronously archive entity data at death."""
        await self._repo.archive(entity_id)
