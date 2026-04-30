# translate_video Package

This package contains the reusable video translation engine. The package should
stay independent from any single interface: CLI, UI, and future webhooks all
call into this code.

Current scope:

- `core/`: project schemas, configuration, artifact storage, and webhook event
  contracts.
