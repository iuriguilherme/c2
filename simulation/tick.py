import asyncio
import logging
import random
from genetics.models import GeneType, Genome
from agents.output import AgentOutput
from agents.pool import ModelPool
from environment.void import VoidEnvironment
from neural.pool import NeuronPool
from neural.brain import Brain
from simulation.entity import Entity
from simulation.archive import EntityArchive
from storage.redis import RedisEntityRepository, RedisTickStream

logger = logging.getLogger(__name__)


class TickEngine:
    def __init__(
        self,
        repo: RedisEntityRepository,
        stream: RedisTickStream,
        void: VoidEnvironment,
        model_pool: ModelPool,
        neuron_pool: NeuronPool | None = None,
        reproduction_handler=None,
        spawn_rate_cap_percent: float = 5.0,
    ) -> None:
        self._repo = repo
        self._stream = stream
        self._void = void
        self._model_pool = model_pool
        self._neuron_pool = neuron_pool or NeuronPool.load()
        self._reproduction_handler = reproduction_handler
        self._spawn_rate_cap_percent = spawn_rate_cap_percent
        self._spawn_queue: list[Entity] = []
        self._archive = EntityArchive(repo)
        self.current_tick = 0

    async def tick(self, tick: int) -> None:
        self.current_tick = tick
        entity_ids = await self._repo.list_living()

        # Process all living entities concurrently
        tasks = [self._process_entity(eid, tick) for eid in entity_ids]
        await asyncio.gather(*tasks, return_exceptions=True)

        # Process spawn queue governed by cap
        max_spawns = max(1, int(len(entity_ids) * (self._spawn_rate_cap_percent / 100.0)))
        spawn_tasks = []
        while self._spawn_queue and len(spawn_tasks) < max_spawns:
            parent = self._spawn_queue.pop(0)
            if self._reproduction_handler is not None:
                spawn_tasks.append(
                    asyncio.create_task(
                        self._reproduction_handler.spawn_offspring(parent, tick=self.current_tick)
                    )
                )

        if spawn_tasks:
            # Let the spawned tasks start executing
            await asyncio.sleep(0)

        self._void.age_messages()
        await self._stream.publish_tick(tick=tick, entity_count=len(entity_ids))

    async def _process_entity(self, entity_id: str, tick: int) -> None:
        data = await self._repo.load(entity_id)
        if not data or data.get("alive") != "True":
            return

        entity = self._load_entity(data)

        # Increment age
        entity.age += 1

        # Check lifespan
        lifespan = entity.genome.get(GeneType.LIFESPAN)
        if entity.age >= lifespan:
            entity.alive = False
            await self._repo.save(entity_id, entity.to_storage_dict())
            await self._archive.archive(entity_id)
            self._void.remove_entity(entity_id)
            return

        # Execute cached action from previous tick
        if entity.cached_action and entity.cached_action_tick >= 0:
            await self._execute_action(entity, entity.cached_action)
            # Clear the cached action so it only executes once
            entity.cached_action = ""
            entity.cached_action_tick = -1

        # Decide whether to think this tick
        if entity.should_think(tick):
            entity.last_think_tick = tick
            nearby = self._void.get_nearby(entity_id, radius=100.0)
            messages = [
                {
                    "from_entity": m["from_entity"],
                    "content": m["content"],
                    "ticks_ago": m["ticks_ago"],
                }
                for m in self._void.get_messages(entity_id)
            ]
            repro_threshold = entity.genome.get(GeneType.REPRODUCTION_THRESHOLD)
            manifest = entity.brain.generate_manifest(
                agent_id=entity_id,
                tick=tick,
                context={"nearby_entities": nearby, "received_messages": messages},
                current_age=entity.age,
                reproduction_threshold=repro_threshold,
            )
            manifest_json = manifest.model_dump_json()

            provider = self._model_pool.get_provider(entity.provider_name)
            if provider:
                raw = await self._collect_llm_response(
                    provider=provider,
                    model=entity.model,
                    system_prompt=entity.system_prompt,
                    user_prompt=entity.user_prompt or "What will you do this tick?",
                    manifest_json=manifest_json,
                )
                output = AgentOutput.parse_llm_response(raw)
                if output:
                    if output.is_valid_for_manifest(manifest):
                        entity.cached_action = raw
                        entity.cached_action_tick = tick
                    if output.user_prompt_update:
                        entity.user_prompt = output.user_prompt_update

        await self._repo.save(entity_id, entity.to_storage_dict())

    async def _collect_llm_response(
        self, provider, model: str, system_prompt: str, user_prompt: str, manifest_json: str
    ) -> str:
        chunks = []
        try:
            async for chunk in provider.generate(
                model=model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                manifest_json=manifest_json,
            ):
                chunks.append(chunk)
        except Exception as e:
            logger.warning("LLM call failed for model %s: %s", model, e)
        return "".join(chunks)

    async def _execute_action(self, entity: Entity, cached_raw: str) -> None:
        output = AgentOutput.parse_llm_response(cached_raw)
        if not output or not output.action:
            return
        action = output.action
        if action.type == "locomotion":
            direction = action.parameters.get("direction", "north")
            distance = float(action.parameters.get("distance", 10.0))
            if direction not in ("north", "south", "east", "west"):
                return
            new_pos = self._void.move(entity.id, direction=direction, distance=distance)
            entity.position_x = new_pos.x
            entity.position_y = new_pos.y
        elif action.type == "signal_emitter":
            message = str(action.parameters.get("message", ""))
            radius = float(action.parameters.get("radius", 50.0))
            self._void.broadcast(entity.id, message=message, radius=radius)
        elif action.type == "divide":
            if self._reproduction_handler is not None:
                logger.debug("Entity %s triggered divide — queuing for offspring spawn", entity.id)
                # Check to avoid duplicate queuing if already queued
                if not any(e.id == entity.id for e in self._spawn_queue):
                    self._spawn_queue.append(entity)

    def _load_entity(self, data: dict) -> Entity:
        genome = Genome.model_validate_json(data["genome"])
        brain = Brain.from_genome(
            genome, self._neuron_pool, rng=random.Random(hash(data["id"]) % (2**31))
        )
        return Entity(
            id=data["id"],
            genome=genome,
            brain=brain,
            system_prompt=data.get("system_prompt", ""),
            user_prompt=data.get("user_prompt", ""),
            model=data.get("model", ""),
            provider_name=data.get("provider", ""),
            position_x=float(data.get("position_x", 0.0)),
            position_y=float(data.get("position_y", 0.0)),
            age=int(data.get("age", 0)),
            alive=data.get("alive") == "True",
            think_interval=int(data.get("think_interval", 5)),
            last_think_tick=int(data.get("last_think_tick", 0)),
            cached_action=data.get("cached_action", ""),
            cached_action_tick=int(data.get("cached_action_tick", -1)),
        )
