# Testing Strategy

## Goals

The test system must protect the translation engine while development moves from
core to CLI and UI. Every functional change gets tests at the lowest level that
can prove it, then broader tests when modules start working together.

## Test Levels

### Unit Tests

Scope:

- config parsing and validation;
- schemas and serialization;
- artifact path generation;
- provider-independent text/timing utilities;
- webhook event payloads.

Rules:

- Run before every commit.
- Keep tests deterministic and fast.
- Use small fixtures and no network calls.

Command:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests/unit
```

Temporary command until the tree is split:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```

### Integration Tests

Scope:

- project store plus artifacts;
- pipeline stage runner with fake providers;
- CLI command invoking core services;
- webhook payload creation during stage execution.

Rules:

- Run before every commit together with unit tests.
- Use fake providers by default.
- Media fixtures must be tiny and committed only when necessary.

Planned command:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests/integration
```

### E2E Tests

Scope:

- full CLI job on tiny media fixture;
- future UI smoke flow;
- future API job lifecycle flow.

Rules:

- Required before `develop -> master`.
- May be slower than integration tests, but must remain practical locally.
- External provider E2E tests must be opt-in.

Planned command:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests/e2e
```

### Load Tests

Scope:

- concurrent project creation;
- artifact writes under parallel jobs;
- batch translation scheduling;
- future queue and API pressure.

Rules:

- Required before `develop -> master`.
- Use generated local fixtures.
- Capture runtime and resource notes in the test output or report.

Planned command:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests/load
```

## Merge Gates

Before every commit:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
python3 -m compileall -q src tests
git diff --check
```

Before merging a task branch into `develop`:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests/unit
PYTHONPATH=src python3 -m unittest discover -s tests/integration
```

Before merging `develop` into `master`:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests/unit
PYTHONPATH=src python3 -m unittest discover -s tests/integration
PYTHONPATH=src python3 -m unittest discover -s tests/e2e
PYTHONPATH=src python3 -m unittest discover -s tests/load
```

Until all directories exist, use the current all-tests command as the active
gate.
