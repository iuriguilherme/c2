---
title: LLM Usage Log Regression Fixes
category: runtime-errors
date: 2026-04-18
tags: [fastapi, redis, simulation, backend]
---

# LLM Usage Log Regression Fixes

## Problem Description
The initial implementation of the LLM usage logging feature introduced several critical regressions that broke both the API and the simulation engine. The API would not start due to syntax errors, and the simulation engine crashed due to uninitialized variables and redundant execution calls. Additionally, MongoDB connectivity issues blocked the entire system during development.

## Root Cause
1.  **Syntax Artifacts**: Accidental insertion of text (`ct:`) and duplicate return statements in `api/main.py` during automated code generation.
2.  **Missing Initialization**: The `TickEngine` constructor was updated to require `llm_log_stream`, but the corresponding instantiation was missing in `engine.py`.
3.  **Redundant Entry Points**: Multiple `asyncio.run(main())` calls were present in `engine.py`.
4.  **Hard Dependencies**: The system was hard-coded to fail if MongoDB was unavailable, making development and testing brittle in environments without a full database stack.

## Solution
1.  **Backend Cleanup**: Surgically removed syntax artifacts from `api/main.py` and restored valid FastAPI lifespan logic.
2.  **Engine Robustness**:
    -   Instantiated `RedisLLMLogStream` in `engine.py` and properly passed it to the `TickEngine`.
    -   Removed duplicate execution calls.
    -   Implemented a `fakeredis` fallback for the simulation engine to ensure it can run even if the primary Redis server is unreachable.
3.  **Optional Persistence**: Wrapped MongoDB/Beanie initialization in try-except blocks across `api/main.py` and `engine.py`. The system now issues a warning but proceeds with limited functionality if MongoDB is missing.
4.  **Sorting Optimization**: Updated `RedisLLMLogStream` to sort logs by the full Redis ID string (`timestamp-sequence`) rather than just the integer timestamp. This ensures correct sub-millisecond ordering for events occurring in the same tick.

## Prevention
-   **Run Tests Before Commit**: Always execute the relevant unit and integration tests (`pytest tests/test_tick_engine.py`) immediately after updating core class constructors.
    (auto memory [claude])
-   **Graceful Degradation**: Design infrastructure components (DBs, Caches) to be optional or have mock fallbacks during the bootstrapping phase to improve developer velocity.
-   **Full-ID Sorting**: When using Redis Streams for chronological logging, always sort by the full message ID to preserve sub-millisecond event sequence.
