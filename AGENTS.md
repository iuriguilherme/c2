## Compound Engineering Workflows

This repository uses Compound Engineering to track decisions and scale knowledge:

- `docs/brainstorms/` — captures product-level requirements and scope decisions using `/ce:brainstorm`. Completed brainstorms should be archived in `docs/brainstorms/archive/`.
- `docs/plans/` — technical implementation plans created using `/ce:plan`. Once implemented and verified, plans should be moved to `docs/plans/archive/`.
- `docs/ideation/` — open-ended notes, research, and deferred feature ideas.

## Efficiency & Communication

- **Caveman Mode** — use `caveman` skill whenever applicable to minimize token usage and keep communication terse.

## Versioning & Tagging

- **SemVer** — use `vX.Y.Z` prefix for git tags.
- **Rules**:
  - `feat`: increment minor (`v0.Y.0`).
  - `fix`: increment patch (`v0.0.Z`).
  - `docs`: do NOT tag.
  - No tagging for chore/refactor unless public API changes.

## Documented Solutions

`docs/solutions/` — documented solutions, architecture decisions, and best practices organized by category with YAML frontmatter (`module`, `tags`, `problem_type`). Relevant when implementing or debugging in documented areas. Create these using `/ce:compound`.
