import random
from genetics.reproduction import reproduce
from genetics import GenePool
from simulation.entity import Entity
from simulation.factory import EntityFactory
from storage.redis import RedisEntityRepository
from agents.pool import ModelPool
from neural.pool import NeuronPool
from environment.void import VoidEnvironment, Position


class ReproductionHandler:
    def __init__(
        self,
        repo: RedisEntityRepository,
        void: VoidEnvironment,
        factory: EntityFactory,
        gene_pool: GenePool,
        model_pool: ModelPool,
    ) -> None:
        self._repo = repo
        self._void = void
        self._factory = factory
        self._gene_pool = gene_pool
        self._model_pool = model_pool
        self._entity_counter = 0

    async def spawn_offspring(
        self,
        parent: Entity,
        tick: int,
        rng: random.Random | None = None,
    ) -> Entity:
        r = rng or random.Random()
        offspring_genome = reproduce(parent.genome, pool=self._gene_pool, rng=r)
        self._entity_counter += 1
        offspring_id = f"offspring-{tick}-{self._entity_counter}"
        assignment = self._model_pool.assign_random(rng=r)
        offspring = self._factory.create(
            entity_id=offspring_id,
            genome=offspring_genome,
            model_assignment=assignment,
            rng=r,
            parent_user_prompt=parent.user_prompt,
        )
        # Spawn near parent
        parent_pos = self._void.get_position(parent.id) or Position(500.0, 500.0)
        offspring.position_x = parent_pos.x + r.uniform(-20, 20)
        offspring.position_y = parent_pos.y + r.uniform(-20, 20)
        await self._repo.save(offspring_id, offspring.to_storage_dict())
        self._void.set_position(
            offspring_id, Position(offspring.position_x, offspring.position_y)
        )
        return offspring
