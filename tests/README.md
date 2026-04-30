# Tests

Tests are focused on behavior added in the same milestone. Run the current suite
with:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```

Keep fixtures small and avoid media files unless a test specifically requires
them.
