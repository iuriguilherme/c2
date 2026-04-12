---
title: Plan Lifecycle Verification and Archival
date: 2026-04-12
type: knowledge
category: docs/solutions/workflow-issues/
module: simulation
problem_type: workflow_issue
component: development_workflow
severity: low
applies_when:
  - A feature branch is fully implemented but the corresponding plan document still carries status: active
  - Periodic housekeeping is needed at the start of a sprint or release cycle
  - An implementation review (ce-review) has produced advisory findings that must survive session end
root_cause: missing_workflow_step
resolution_type: workflow_improvement
symptoms:
  - Plan document status field not updated to complete despite all units being implemented
  - Active plans accumulate in docs/plans/ after their work is merged
  - Advisory findings from implementation review are lost at branch merge or session end
tags:
  - plan-lifecycle
  - archival
  - workflow
  - todos
  - documentation
status: verified
---

# Plan Lifecycle Verification and Archival

## Context

Plans in `docs/plans/` can fall out of sync with the codebase. Implementation finishes on a feature branch, but the plan document retains `status: active` with all unit checkboxes unchecked. Without a periodic lifecycle check, stale active plans accumulate and obscure actual work-in-progress, and advisory findings from the implementation review get lost if they are not captured before the branch is merged.

This was encountered after the AGI simulation V1 completion sprint: `2026-04-10-002-feat-agi-simulation-completion-plan.md` had `status: active` and five unchecked units, but all five units were verified present in the merged code.

## Guidance

### Step 1 — List all active plans

```bash
ls docs/plans/
```

Open each file and check its `status:` field in YAML frontmatter. Skip files already in `docs/plans/archive/`.

### Step 2 — Verify implementation against the code, not the checkboxes

Cross-reference each unit against the actual files. Use targeted greps — do not trust the plan doc's checkbox state:

```bash
# Example: verify divide/removal logic is wired
grep -n "divide\|ReproductionHandler\|remove_entity" simulation/tick.py

# Example: verify a module was consolidated (old file deleted)
ls genetics/pool.py                                      # expect: No such file
grep -rn "from genetics import" simulation/ engine.py    # expect: unified imports

# Example: verify config artefacts are present
ls .env.example pyproject.toml
```

A plan unit is implemented when all its code evidence is present. A passing grep is sufficient; running the full test suite is not required at this stage.

### Step 3 — Archive complete plans

If all units are implemented, move the plan to archive:

```bash
mv docs/plans/<filename>.md docs/plans/archive/
```

Do this even if the plan document was never updated to `status: complete` — the code is the authoritative record.

### Step 4 — Capture deferred advisory items as todos

Before archiving, collect any advisory findings from ce-review or implementation notes that were not acted on. Write them into a dated todo file rather than leaving them as comments in the plan or in code:

```
docs/todos/YYYY-MM-DD-<slug>-followup.md
```

Each item should state: **what** to change, **where**, and **why**. Concrete todo entries from AGI simulation V1:

```markdown
## 1. Replace global `_redis_client` with `app.state.redis`
File: api/main.py, api/routes/entities.py
Why: Module-level mutation makes parallel test isolation hard.

## 2. Add authentication to GET /entities/archived/{entity_id}
File: api/routes/entities.py
Why: Currently unauthenticated — all entity history is readable.

## 3. Wire data/prompts/system_template.j2 into EntityFactory
File: simulation/factory.py
Why: Template exists but factory still uses inline f-strings; two sources of truth.
```

### Step 5 — If a plan is genuinely incomplete

Update the checkboxes to reflect what is and is not done. Leave the file in `docs/plans/`. Do not archive.

## Why This Matters

Plan documents are not updated atomically with commits. Implementation work happens on feature branches; the plan doc is often the last thing touched — or never updated at all. A plan that reads `status: active` with empty checkboxes is ambiguous: it might be 100% done or 0% done. The only reliable signal is the code.

Archiving completed plans keeps `docs/plans/` as a true work-queue. If it contains stale entries, engineers treating it as a queue will re-examine already-completed work or lose trust in the queue entirely.

Capturing advisory findings in `docs/todos/` before archiving is the handoff point between "done" and "done well." Without it, findings exist only in ephemeral session context and are lost at branch merge or session end.

## When to Apply

- Before merging a feature branch that corresponds to a plan in `docs/plans/`
- During periodic housekeeping when multiple plans may have been silently completed
- Whenever a plan's `status:` field is suspected to be stale relative to the actual codebase
- After a ce-review advisory session produces findings against an in-progress plan

Do not apply mechanically to every commit — only when a plan's implementation scope is plausibly complete.

## Examples

**Plan complete but doc never updated:**

`docs/plans/2026-04-10-002-feat-agi-simulation-completion-plan.md` had `status: active` and five unchecked units. Grepping the codebase confirmed all five units were present in merged code:

```bash
# Unit 1 — tick engine wiring
grep -n "divide\|ReproductionHandler\|remove_entity" simulation/tick.py
# → 3 matches found

# Unit 2 — GenePool consolidation
ls genetics/pool.py    # → No such file or directory
grep -rn "from genetics import" simulation/ engine.py    # → 4 unified imports

# Unit 3 — archive endpoint live
grep -n "archived" api/routes/entities.py    # → route present, not 501

# Unit 4 — eviction and null guard
grep -n "age_messages\|is_valid_for_manifest" agents/output.py    # → both present

# Unit 5 — config artefacts
ls .env.example pyproject.toml    # → both found
```

Both plans archived:

```bash
mv docs/plans/2026-04-10-002-feat-agi-simulation-completion-plan.md docs/plans/archive/
mv docs/plans/2026-03-26-001-feat-agi-entity-simulation-v1-plan.md docs/plans/archive/
```

Advisory findings written to `docs/todos/2026-04-12-agi-simulation-v1-followup.md`.

**Distinguishing complete vs. incomplete units:**

If a grep returns no output for a required symbol, that unit is not implemented. Leave the plan active, check the passing units, leave the failing ones unchecked. Do not archive until all units pass.

**What belongs in todos vs. a new plan:**

A todo item is a single bounded change with a known location (replace one pattern, add one guard, wire one unused file). If the advisory finding requires architectural design, new module creation, or coordination across layers, it warrants a new plan rather than a todo entry.

## Related

- [AGI Entity Simulation V1 Architecture](../best-practices/agi-entity-simulation-v1-architecture-2026-04-11.md) — the architecture doc this workflow was applied to verify
- `docs/plans/archive/` — destination for completed plans
- `docs/todos/2026-04-12-agi-simulation-v1-followup.md` — example todo file produced by this workflow
