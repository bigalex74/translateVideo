# Tests

Tests are focused on behavior added in the same milestone. Run the current suite
with:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```

Keep fixtures small and avoid media files unless a test specifically requires
them.

Current levels:

- `unit/`: pure and deterministic tests, including core schemas and store logic.
- `integration/`: fake-provider tests across multiple internal modules.
- `e2e/`: future user-facing CLI/API/UI smoke flows.
- `load/`: future concurrency and resource tests.
