# Core

The core package contains interface-neutral project models and persistence
helpers. It must not import CLI, UI, MoviePy, Whisper, or TTS providers.

Core responsibilities:

- language-agnostic translation configuration;
- segment and project schemas;
- deterministic artifact paths;
- future webhook event contracts for n8n/API orchestration.
