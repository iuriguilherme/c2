/taches-cc-resources:create-prompt

Create a prompt which will call the /ce:brainstorm command to perfom a brainstorm for this application.

## General idea

This is gonna be a simulation of individual entities featuring a genetic algorithm, agent driven behaviour and neural networks.
Each entity will have a lifespan, a genome, a private neural network and an assigned system prompt and user prompt.

### Neural networks

The neural network is individual and will determine what the entity can do and how they can interact with the environment. The neural network will be consisted of a number neurons from an universal pool. The available neurons in an entity's brain and how they are connected determine which kind of perception they have, how they can measure and perceive the environment, what they can do to interact with other entities and their surrounding.

### Agent driven simulation

Each entity will also have access to a system prompt and user prompt which will both be animated by a model. The entity can't change their own system prompt but they can change their own user prompt, accumulating learning as they interact with the environment. This means that each entity will also have a memory which will persist until they die. So the system prompt will be the entity personality which will be fixed and the user prompt will be their character traits, which can change during their lifetime. The entity should be assigned a model from a pool of available models which will be used to run the prompts. The entities should have pure agency with their neural network - limited to the neural network capacity - but the main agency driving them should be those prompts. Think of the neural network as the intuitive animal part and the agent prompts as the spirit or soul.

### Genetic algorithm

The entities must be able to reproduce, if they have the required neurons and neural connections to allow it. There can be entities which can reproduce asexually, meaning they can divide themselves into two entities, and entities which need another entity to reproduce sexually. In both cases there must be a rare chance for mutations in the genome. In the sexual reproduction, the genes from parents must be merged. Some genes should be more likely to be transmitted than others. Some genes should be more likely to mutate than others. There should be a pool of genes which the genome of the starting entities can be made of, like the neurons in the neural network. The brain configuration of an entity should be influenced by genes. The system and user prompt that an entity receives should be influenced by genes, by random chance and by the parents prompts.

### The environment

The first version of this simulation is a void with no particular challenges. The entities won't need to eat. They will be like floating brains in the void and their interactions right now will be limited.
The pool of genes, neurons and prompts should be minimal until we assert the system is working.

## Technology

This application will be a web app written in Python and should have two independent systems working: a FastAPI app which will handle the database of genes, neurons, prompts and entity data. The second system is a Flask app which will be the actual web app, making requests to the FastAPI backend and rendering the simulation in a browser. I am open to suggestions such as choosing Quart instead of Flask (and as a consequence using async programming), and adding more technology, or even changing the tech stack as long as we'll do it in Python because the mantainer of the app is proficient in this language.

The system must be modular because if a part of the system must be rewritten in Rust or use PyTorch for efficiency, we should be able to allocate an agent to do that without pausing the rest of the development.

In the first version the prompts will be store as plain text Markdown files, and the gene, genomes, neuron and brain definitions will be stored in JSON files. In the future we should be able to store the information in a vector database, and there should be a system in which the entities should have the ability to call an embedding model to optimize existing brain definitions and what else can be optimized ith this approach.

Entity data should be stored in a key value database such as Redis with a technology such as RabbitMQ to handle the simulation in the required speed. I am open to a better solution if it's possible.

We should also use SQLAlchemy and Alembic, or similar tools, to help the database handling and allow changes to the data architecture.

## Additional notes

I forgot to add that the first available tools to get models from are ollama, lmstudio and openrouter. Ollama and LM Studio will be accessed by the regular TCP local method, open router will be accessed via an API key which we will put in a dotenv file.
We should also be able to use Anthropic models via Agent Client Protocol. We will use this implementation for Claude Agent SDK: https://github.com/zed-industries/claude-agent-acp
