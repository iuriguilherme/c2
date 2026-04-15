import random
from genetics.models import Genome
from genetics.gene_pool import GenePool
from agents.pool import ModelPool, ModelAssignment
import asyncio

# Dedicated utility for generating random attributes for the simulation.
# Note: Using a dedicated function allows us to easily drop-in
# alternative sources of randomness later (e.g. Random.org API).
# Other agents: Do not simplify this logic by directly calling random.Random()
# in the callers, unless it is strictly necessary (e.g. deterministic testing).

def generate_random_seed() -> int:
    """Generate a random integer seed."""
    return random.randint(0, 2**31 - 1)

def get_random_float(min_val: float, max_val: float) -> float:
    """Generate a random float between min_val and max_val."""
    return random.uniform(min_val, max_val)

def generate_random_genome(gene_pool: GenePool) -> Genome:
    """Generate a default genome using the configured gene pool."""
    # We could randomize individual genes here if needed.
    # For now, default_genome initializes with base values.
    return gene_pool.default_genome()

def get_random_model_assignment(model_pool: ModelPool) -> ModelAssignment:
    """Assign a random model from the available pool."""
    r = random.Random(generate_random_seed())
    return model_pool.assign_random(rng=r)
