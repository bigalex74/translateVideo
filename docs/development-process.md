# Development Process

## Branching

Use the project git-flow adapted from the LightRAG knowledge base:

- `master`: stable baseline.
- `develop`: integration branch for active development.
- `TVIDEO-XXX-short-name`: feature and task branches.
- `release/<version>`: stabilization before a tagged release.
- `hotfix/<name>`: urgent fixes from stable.

Branch names use an incrementing project task number:

```text
TVIDEO-001-core-architecture
TVIDEO-002-cli-foundation
TVIDEO-003-editable-artifacts
```

All development branches merge into `develop`. After all release gates pass,
`develop` merges into `master`.

Before starting a task:

```bash
git checkout develop
git pull --ff-only origin develop
git checkout -b TVIDEO-XXX-short-name
```

## Commit Rules

- Commit each meaningful milestone.
- Keep commits scoped: docs, core model, CLI, UI, tests, or refactor.
- Do not mix formatting churn with behavior changes.
- Do not rewrite shared history unless explicitly requested.
- Preferred commit format:
  `TVIDEO-XXX - краткое описание до 8 слов`.

## Versioning

Use semantic versioning:

- `0.x`: active design and API evolution.
- `MAJOR`: incompatible public API or artifact format change.
- `MINOR`: new capabilities.
- `PATCH`: fixes with compatible behavior.

The current version is stored in `VERSION`.

Every change merged into `master` must update `VERSION` and `change.log`:

- `PATCH`: small fix or bug fix.
- `MINOR`: compatible behavior, process, or feature change.
- `MAJOR`: incompatible behavior or manual migration.

The first planned internal versions:

- `0.1.0`: core project model and artifact store.
- `0.2.0`: CLI around the existing translation pipeline.
- `0.3.0`: editable artifacts, subtitles, and resume support.
- `0.4.0`: local UI.
- `0.5.0`: webhook/API layer for external orchestration.

## Testing

- Every code change must include focused tests for the changed behavior.
- Do not modify unrelated tests to force a new implementation through.
- Fixtures must stay small and deterministic.
- Before every commit: run the full unit and integration suites.
- Before every branch merge into `develop`: run full unit and integration suites.
- Before every `develop` merge into `master`: run unit, integration, E2E, and load
  test suites.

Test levels:

- Unit tests: deterministic tests for pure functions, schemas, adapters, and
  validation.
- Integration tests: multiple internal modules together, real artifact layout,
  small local files, no heavy external services by default.
- E2E tests: user-facing flows through CLI/API/UI using tiny media fixtures.
- Load tests: throughput, concurrency, large-job behavior, queue pressure, and
  resource usage.

Current command while only unit tests exist:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```

Current syntax check:

```bash
python3 -m compileall -q src tests
```

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
