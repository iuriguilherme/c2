---
title: Local providers are not working
date: 2026-04-18
topic: llm-provider
status: open
source: user
priority: low
---

Local providers are not working.

# LM Studio

LMStudio doesn't work in our current implementation.

In the development environment, LMStudio is running in the default port but it doesn't get used.

In the error log (route /llm-providers of the web app), I get the following errors:

```
5:24:14 PM	LMStudioProvider	smollm2-1.7b-instruct	ERROR	All connection attempts failed (6ms)
```

This can mean that the docker container cannot access the LM Studio being run in the hypervisor because LMStudio runs on 127.0.0.1 and not on 0.0.0.0, or the LM Studio settings being wrong. This needs to be diagnosed.

We need to decide if we need to run LMStudio in a docker container like Ollama or if there's a way to fix the current workflow. In any case, it would be nice to have the option to run LMStudio on docker as well.

# Ollama

Ollama is running in a docker container and is working properly. But the entities trying to use Ollama produce this error message:

```
5:28:05 PM	OllamaProvider	smollm2:135m	ERROR	Client error '404 Not Found' for url 'http://ollama:11434/api/chat' For more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/404 (24ms)
```

This most likely means that the ollama related functions in our API are using Ollama incorrectly. The only API endpoint Ollama have is /generate. There was never a /chat endpoint. Hence, the 404 error is to be expected. Ollama docs: https://docs.ollama.com/api/introduction

# Other thoughts

We need to see the URL settings for LLM providers in the settings page and even be able to edit them, and the changes should be persistent across resets.

We need to be able to choose to run Ollama and/or LMstudio with Docker and we should be able to choose not to activate one or more of these providers if we're running them in the host machine.
