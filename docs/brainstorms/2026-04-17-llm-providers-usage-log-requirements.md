---
date: 2026-04-17
topic: llm-providers-usage-log
---

# LLM Providers & Usage Log

## Problem Frame
Currently, there's no visibility into real-time LLM usage or provider failures from the web interface. If a provider like LM Studio is failing or misconfigured, it's hard to debug without diving into backend logs. Furthermore, the existing settings page is mostly dedicated to LLM provider configuration (since neural settings were split out), but is generically named "Settings".

## Requirements
- R1. **Rename the page**: Rename the "Settings" page (and its navigation links) to "LLM Providers".
- R2. **LLM Usage Log**: Add a new table/section to the "LLM Providers" page that displays recent LLM requests and their status.
- R3. **Error Persistence**: Successful requests can rotate out over time, but error logs must *not* rotate out rapidly. They should accumulate up to a generous hard cap (e.g., 1000 errors) to prevent performance issues while ensuring they aren't missed.
- R4. **Error Details**: Provide actionable error details within the log to help debug failing providers.
- R5. **Clear Errors Button**: Include a button to manually clear the accumulated error logs.

## Success Criteria
- A user can immediately see if their configured LM Studio (or any other provider) is rejecting requests or timing out by looking at the LLM Providers page.
- The navigation clearly points to "LLM Providers" instead of a generic "Settings" page.

## Scope Boundaries
- This is a UI observability feature. It does not change how providers authenticate, nor does it implement a heavy, full-scale log aggregation system (like ELK stack).
- Does not cover logging general application errors, only LLM provider interactions.

## Outstanding Questions
- None.

## Next Steps
→ `/ce:plan` for structured implementation planning
