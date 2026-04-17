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
from storage.redis import RedisEntityRepository, RedisTickStream, RedisInteractionStream, RedisLLMLogStream

logger = logging.getLogger(__name__)


class TickEngine:
    def __init__(
        self,
        repo: RedisEntityRepository,
        stream: RedisTickStream,
        interaction_stream: RedisInteractionStream,
        void: VoidEnvironment,
        model_pool: ModelPool,
        llm_log_stream: RedisLLMLogStream,
        neuron_pool: NeuronPool | None = None,
        reproduction_handler=None,
        spawn_rate_cap_percent: float = 5.0,
    ) -> None:
        self._repo = repo
        self._stream = stream
        self._interaction_stream = interaction_stream
        self._void = void
        self._model_pool = model_pool
        self._llm_log_stream = llm_log_stream
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
                elif result:
                    # Successfully spawned
                    await self._interaction_stream.publish_interaction(
                        event_type="birth",
                        source_id=parent_id,
                        message=f"Parent {parent_id} spawned offspring {result.id}",
                        extra_data={"offspring_id": result.id}
                    )

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
            await self._interaction_stream.publish_interaction(
                event_type="death",
                source_id=entity_id,
                message=f"Entity {entity_id} died of old age at {entity.age}"
            )
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
            
            entity.brain.evaluate({"cortex_input_receiver": entity.cortex_signal})
            entity.cortex_signal = 0.0
            
            manifest = entity.brain.generate_manifest(
                agent_id=entity_id,
                tick=tick,
                context={"nearby_entities": nearby, "received_messages": messages},
                current_age=entity.age,
                reproduction_threshold=repro_threshold,
            )
            import json
            
            clarity = entity.genome.get(GeneType.COGNITIVE_CLARITY)
            if clarity > 0.8:
                # Need to dump to dict first to apply indent
                manifest_json = json.dumps(manifest.model_dump(), indent=2)
            elif clarity > 0.4:
                manifest_json = manifest.model_dump_json()
            else:
                raw_json = manifest.model_dump_json()
                manifest_json = "".join(
                    " " if c in "{}[]\"" else c 
                    for c in raw_json
                )
                
            entity.neural_system_prompt = manifest_json
            
            entity.last_manifest = manifest.model_dump_json()
            entity.last_activations = json.dumps([n.activation for n in entity.brain.neurons])

            provider = self._model_pool.get_provider(entity.provider_name)
            if provider:
                user_prompt = entity.user_prompt or "What will you do this tick?"
                raw = await self._collect_llm_response(
                    provider=provider,
                    model=entity.model,
                    system_prompt=entity.system_prompt,
                    user_prompt=user_prompt,
                    manifest_json=manifest_json,
                )
                
                # Capture LLM exchange
                exchange = {
                    "system": entity.system_prompt,
                    "user": user_prompt,
                    "manifest": manifest.model_dump(),
                    "response": raw
                }
                entity.last_llm_exchange = json.dumps(exchange)

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
        import time
        start_time = time.time()
        chunks = []
        try:
            async for chunk in provider.generate(
                model=model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                manifest_json=manifest_json,
            ):
                chunks.append(chunk)
            
            duration_ms = int((time.time() - start_time) * 1000)
            await self._llm_log_stream.publish_log(
                provider=provider.__class__.__name__,
                model=model,
                success=True,
                duration_ms=duration_ms,
                details="OK"
            )
        except Exception as e:
            logger.warning("LLM call failed for model %s: %s", model, e)
            duration_ms = int((time.time() - start_time) * 1000)
            await self._llm_log_stream.publish_log(
                provider=provider.__class__.__name__,
                model=model,
                success=False,
                duration_ms=duration_ms,
                details=str(e)
            )
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
            if distance > 1.0:
                await self._interaction_stream.publish_interaction(
                    event_type="movement",
                    source_id=entity.id,
                    message=f"Entity {entity.id} moved {direction} by {distance:.1f}",
                    extra_data={"direction": direction, "distance": distance}
                )
        elif action.type == "signal_emitter":
            message = str(action.parameters.get("message", ""))
            radius = float(action.parameters.get("radius", 50.0))
            self._void.broadcast(entity.id, message=message, radius=radius)
            await self._interaction_stream.publish_interaction(
                event_type="signal",
                source_id=entity.id,
                message=f"Entity {entity.id} broadcasted: '{message}' (radius: {radius:.1f})",
                extra_data={"content": message, "radius": radius}
            )
        elif action.type == "divide":
            if self._reproduction_handler is not None:
                logger.debug("Entity %s triggered divide — queuing for offspring spawn", entity.id)
                # Check to avoid duplicate queuing if already queued
                if entity.id not in self._spawn_queue_ids:
                    self._spawn_queue.append(entity.id)
                    self._spawn_queue_ids.add(entity.id)
        elif action.type == "cortex_write":
            try:
                val = float(action.parameters.get("value", 0.0))
                entity.cortex_signal = max(-1.0, min(1.0, val))
            except (ValueError, TypeError):
                entity.cortex_signal = 0.0

    def _load_entity(self, data: dict) -> Entity:
        genome = Genome.model_validate_json(data["genome"])
        brain = Brain.from_genome(
            genome, self._neuron_pool, rng=random.Random(hash(data["id"]) % (2**31))
        )
        return Entity(
            id=data["id"],
            genome=genome,
            brain=brain,
            base_system_prompt=data.get("base_system_prompt") or data.get("system_prompt", ""),
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
            cortex_signal=float(data.get("cortex_signal", 0.0)),
            cached_action=data.get("cached_action", ""),
            cached_action_tick=int(data.get("cached_action_tick", -1)),
            last_manifest=data.get("last_manifest", ""),
            last_activations=data.get("last_activations", ""),
            last_llm_exchange=data.get("last_llm_exchange", ""),
        )
