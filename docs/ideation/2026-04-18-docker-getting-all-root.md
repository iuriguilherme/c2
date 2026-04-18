---
date: 2026-04-18
topic: docker
---

# Docker containers uses all files from root

All docker containers are using "build ." and relying on the same Dockerfile which is copying the whole repository into each image. This is completely wrong. This should be refactored, only relevant files should be copied to each container and files which needs to be updated both ways should be volumes and not copied into the image.

Each container is a separate application which needs to be isolated and the repository organized accordingly.
