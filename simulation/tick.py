import asyncio
import collections
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
        self._spawn_rate_cap_percent = max(0.0, min(100.0, spawn_rate_cap_percent))
        self._spawn_queue: collections.deque[str] = collections.deque()
        self._spawn_queue_ids: set[str] = set()
        self._archive = EntityArchive(repo)
        self.current_tick = 0

    async def tick(self, tick: int) -> None:
        self.current_tick = tick
        entity_ids = await self._repo.list_living()

        # Process all living entities concurrently
        tasks = [self._process_entity(eid, tick) for eid in entity_ids]
        await asyncio.gather(*tasks, return_exceptions=True)

        # Process spawn queue governed by cap
        max_spawns = max(0, int(len(entity_ids) * (self._spawn_rate_cap_percent / 100.0)))
        spawn_work: list[tuple[str, asyncio.Task]] = []
        while self._spawn_queue and len(spawn_work) < max_spawns:
            parent_id = self._spawn_queue.popleft()
            self._spawn_queue_ids.discard(parent_id)
            if self._reproduction_handler is not None:
                # Reload entity from repo to avoid stale references
                data = await self._repo.load(parent_id)
                if not data or data.get("alive") != "True":
                    logger.debug("Skipping spawn for %s — parent no longer alive", parent_id)
                    continue
                parent_entity = self._load_entity(data)
                spawn_work.append(
                    (
                        parent_id,
                        asyncio.create_task(
                            self._reproduction_handler.spawn_offspring(parent_entity, tick=self.current_tick)
                        ),
                    )
                )

        if spawn_work:
            results = await asyncio.gather(
                *(task for _, task in spawn_work),
                return_exceptions=True,
            )
            for (parent_id, _), result in zip(spawn_work, results):
                if isinstance(result, Exception):
                    logger.error(
                        "Failed to spawn offspring for parent %s on tick %s",
                        parent_id,
                        self.current_tick,
                        exc_info=result,
                    )
                    # Re-queue failed spawns
                    if parent_id not in self._spawn_queue_ids:
                        self._spawn_queue.append(parent_id)
                        self._spawn_queue_ids.add(parent_id)

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

            # Update sensory neurons directly before evaluating
            from neural.models import NeuronType
            for neuron in entity.brain.neurons:
                if neuron.neuron_type == NeuronType.PROXIMITY:
                    # Provide an activation level based on proximity of nearest entity (closer = higher)
                    activation = 0.0
                    if nearby:
                        closest_dist = min(n["distance"] for n in nearby)
                        # Normalize between 0 and 1, assuming max interaction distance of 100
                        activation = max(0.0, 1.0 - (closest_dist / 100.0))
                    neuron.activation = activation
                elif neuron.neuron_type == NeuronType.SIGNAL_RECEIVER:
                    # Higher activation the more messages received
                    activation = min(1.0, len(messages) * 0.2)
                    neuron.activation = activation

            # Pre-evaluate neural network with latest state
            entity.brain.evaluate()

            manifest = entity.brain.generate_manifest(
                agent_id=entity_id,
                tick=tick,
                context={"nearby_entities": nearby, "received_messages": messages},
                current_age=entity.age,
                reproduction_threshold=repro_threshold,
            )

            # Process cognitive clarity for neural system prompt updates
            clarity = entity.genome.get(GeneType.COGNITIVE_CLARITY)
            if clarity > 0.8:
                manifest_json = manifest.model_dump_json(indent=2)
                entity.neural_system_prompt = f"Neural State (High Clarity):\n{manifest_json}"
            elif clarity > 0.4:
                manifest_json = manifest.model_dump_json()
                entity.neural_system_prompt = f"Neural State:\n{manifest_json}"
            else:
                import json
                raw_str = json.dumps(manifest.model_dump())
                # Scramble it slightly
                manifest_json = "".join(c if c not in '"{}:,' else ' ' for c in raw_str)
                entity.neural_system_prompt = f"Sensory noise (Low Clarity):\n{manifest_json}"

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
        elif action.type == "cortex_input_receiver":
            input_val = float(action.parameters.get("input_value", 0.0))
            # Map [-1.0, 1.0] range to [0.0, 1.0] activation range
            mapped_val = (input_val + 1.0) / 2.0
            # Find cortex_input_receiver neuron and set its state
            from neural.models import NeuronType
            for neuron in entity.brain.neurons:
                if neuron.neuron_type == NeuronType.CORTEX_INPUT_RECEIVER:
                    neuron.activation = max(0.0, min(1.0, mapped_val))
        elif action.type == "divide":
            if self._reproduction_handler is not None:
                logger.debug("Entity %s triggered divide — queuing for offspring spawn", entity.id)
                # Check to avoid duplicate queuing if already queued
                if entity.id not in self._spawn_queue_ids:
                    self._spawn_queue.append(entity.id)
                    self._spawn_queue_ids.add(entity.id)

    def _load_entity(self, data: dict) -> Entity:
        genome = Genome.model_validate_json(data["genome"])
        brain = Brain.from_genome(
            genome, self._neuron_pool, rng=random.Random(hash(data["id"]) % (2**31))
        )
        return Entity(
            id=data["id"],
            genome=genome,
            brain=brain,
            base_system_prompt=data.get("base_system_prompt", data.get("system_prompt", "")),
            neural_system_prompt=data.get("neural_system_prompt", ""),
            learned_system_prompt=data.get("learned_system_prompt", ""),
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
            neuron_profile_id=data.get("neuron_profile_id", ""),
        )
