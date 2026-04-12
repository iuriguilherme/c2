---
title: Brainstorm Lifecycle Verification and Archival
date: 2026-04-12
type: knowledge
category: docs/solutions/workflow-issues/
module: simulation
problem_type: workflow_issue
component: development_workflow
severity: low
applies_when:
  - A brainstorm's requirements are suspected to be fully implemented in the codebase
  - Periodic housekeeping of docs/brainstorms/ is needed
  - A new planning cycle is beginning and the brainstorm queue should be audited
tags:
  - brainstorm-lifecycle
  - archival
  - requirements-verification
  - workflow
  - documentation
status: verified
---

# Brainstorm Lifecycle Verification and Archival

## Context

Brainstorm documents in `docs/brainstorms/` define requirements and problem frames before planning begins. After planning and implementation, they can silently become fully satisfied — but without a verification step they remain as open artifacts alongside unfinished work.

This workflow was first applied to `2026-03-26-agi-entity-simulation-requirements.md` (34 requirements across 5 system layers) after all derived plans were archived. The brainstorm's `dependencies/assumptions` section referenced `claude-agent-acp` as a Python dependency, but the implementation used the `anthropic` SDK directly — a discrepancy found only by checking code, not by reading the plan.

See also: [Plan Lifecycle Verification and Archival](plan-lifecycle-verification-and-archival-2026-04-12.md) — the analogous workflow for `docs/plans/`.

## Guidance

### Step 1 — List brainstorms and read each for scope

```bash
ls docs/brainstorms/
```

Skim each brainstorm's requirements list and scope boundaries. The key signal for archival readiness: all items in `## Requirements` are plausibly covered by merged code, and no items in `## Outstanding Questions` are unresolved.

### Step 2 — Verify requirements against code by layer

Cross-check requirement groups in parallel. For a layered system, verify one layer at a time:

```bash
# Neuron types — check catalogue file directly
grep -n "neuron_type" data/neuron_pool.json

# Provider implementation — check actual imports, not assumptions
grep -rn "from anthropic\|import anthropic\|claude-agent-acp" agents/ --include="*.py"

# Core wiring — check that key components are connected
grep -n "divide\|ReproductionHandler\|remove_entity" simulation/tick.py

# Config artefacts — check files exist
ls .env.example pyproject.toml data/neuron_pool.json data/gene_pool.json
```

**Verify dependencies/assumptions too.** A brainstorm may list specific libraries (e.g., `claude-agent-acp`) that were swapped for better alternatives during implementation. Grep for the original name to confirm it was intentionally dropped, not forgotten.

### Step 3 — Cross-check against existing todos

Before adding new todo items, verify that items already in `docs/todos/` are not already done:

```bash
# Example: check if a "missing" test actually exists
grep -rn "test_integration_two_generation\|two.generation" tests/ --include="*.py"
python -m pytest tests/test_tick_engine.py::test_integration_two_generation_via_tick -q
```

A todo marked as missing may have been written later in the implementation sprint. Check the code before adding a duplicate.

### Step 4 — Archive if all requirements satisfied

```bash
mkdir -p docs/brainstorms/archive
mv docs/brainstorms/<filename>.md docs/brainstorms/archive/
```

Deviations from the brainstorm (e.g., a different library than specified) do not block archival if the requirement is functionally satisfied. Record the deviation as a new todo item for documentation rather than leaving the brainstorm open.

### Step 5 — Update todos for any gaps or deviations found

For each gap or deviation found:
- **Fully missing requirement**: create a new plan (not a todo)
- **Minor deviation from spec** (e.g., different library used): add a todo to document the change in the relevant architecture solution doc
- **Todo item already done**: mark it done in the existing todos file

```markdown
## 6. Document R15 provider deviation

Context: Brainstorm specified claude-agent-acp. Implementation used anthropic SDK
directly (agents/providers/anthropic.py). claude-agent-acp is not an installable
Python package.

Action: Add a note in the architecture doc clarifying why the SDK was chosen.
```

## Why This Matters

Brainstorms accumulate silently. Unlike plans (which have explicit unit checkboxes), brainstorms have no built-in completion signal. A brainstorm sitting open alongside unfinished work creates false urgency — it looks like there is more to do than there is.

Verifying dependencies/assumptions in the brainstorm catches specification drift: things that seemed like external dependencies at brainstorm time may have been dropped, replaced, or already built-in by the implementation. Without this check, the deviation lives only in commit history.

The pattern of "verify todos before adding more" prevents accumulating stale task lists. An advisory todo from a code review sprint may already have been resolved in the same sprint.

## When to Apply

- After archiving all derived plans — the brainstorm has served its purpose
- At the start of a V2 planning cycle — audit V1 brainstorms before creating V2 ones
- After a ce-review pass flags deviations from stated design decisions

## Examples

**R15 deviation — dependency never installed:**

Brainstorm said:
```
## Dependencies / Assumptions
- `claude-agent-acp` (https://github.com/zed-industries/claude-agent-acp) is available
  and installable as a Python dependency.
```

Verification:
```bash
grep -rn "claude-agent-acp" agents/ pyproject.toml requirements.txt
# → no output — never referenced
grep -rn "import anthropic" agents/ --include="*.py"
# → agents/providers/anthropic.py:3: import anthropic as sdk
```

Conclusion: R15 is satisfied — the Anthropic provider works. The `claude-agent-acp` dependency was silently dropped in favor of the official `anthropic` SDK. Record as a deviation todo, do not block archival.

**Todo already done — test exists:**

Before adding "missing two-generation test" as a new todo:
```bash
grep -rn "two.generation\|test_integration_two_generation" tests/ --include="*.py"
# → tests/test_tick_engine.py:223: # ── Test 4: Integration — two-generation...
# → tests/test_tick_engine.py:226: async def test_integration_two_generation_via_tick():

python -m pytest tests/test_tick_engine.py::test_integration_two_generation_via_tick -q
# → 1 passed in 0.04s
```

Mark the existing todo item done instead of duplicating it.

## Related

- [Plan Lifecycle Verification and Archival](plan-lifecycle-verification-and-archival-2026-04-12.md) — identical pattern for `docs/plans/`
- [AGI Entity Simulation V1 Architecture](../best-practices/agi-entity-simulation-v1-architecture-2026-04-11.md) — architecture doc where R15 deviation should be documented
- `docs/todos/2026-04-12-agi-simulation-v1-followup.md` — example todos file updated by this workflow
