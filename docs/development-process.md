# Development Process

## Branching

Use a lightweight git-flow:

- `main`: stable public baseline.
- `develop`: integration branch.
- `feature/<name>`: active development.
- `release/<version>`: stabilization before a tagged release.
- `hotfix/<name>`: urgent fixes from stable.

Current work starts on `feature/core-architecture-scaffold`.

## Commit Rules

- Commit each meaningful milestone.
- Keep commits scoped: docs, core model, CLI, UI, tests, or refactor.
- Do not mix formatting churn with behavior changes.
- Do not rewrite shared history unless explicitly requested.

## Versioning

Use semantic versioning:

- `0.x`: active design and API evolution.
- `MAJOR`: incompatible public API or artifact format change.
- `MINOR`: new capabilities.
- `PATCH`: fixes with compatible behavior.

The first planned internal versions:

- `0.1.0`: core project model and artifact store.
- `0.2.0`: CLI around the existing translation pipeline.
- `0.3.0`: editable artifacts, subtitles, and resume support.
- `0.4.0`: local UI.
- `0.5.0`: webhook/API layer for external orchestration.

## Testing

- Every code change must include focused tests for the changed behavior.
- All tests must be run after every change before the next milestone commit.
- Existing tests should not be rewritten to force a new implementation through.
- Fixtures must stay small and deterministic.

## Documentation

- Every project folder has a README that explains ownership and intent.
- Public modules should have concise docstrings.
- Comments should explain decisions or non-obvious code paths.
- Architecture changes must update `docs/architecture.md`.

## Definition of Done

- Code is implemented.
- Tests for changed behavior exist.
- Full test suite is green.
- Documentation is updated.
- Agent wiki notes record review comments for the milestone.
- Changes are committed and pushed to the feature branch.
