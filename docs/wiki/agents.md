# Development Agents

The project uses lightweight review agents as written roles. They leave comments
after meaningful milestones. Later these roles can map to real automated agents.

## Roles

### Product Owner Agent

Owns user value, workflow clarity, and scope control.

### Analyst Agent

Owns requirements, edge cases, and acceptance criteria.

### Architect Agent

Owns boundaries, artifact contracts, and long-term maintainability.

### Translation Agent

Owns translation quality, style, language handling, and glossary behavior.

### Timing Agent

Owns segment duration, speech density, timing fit, and overlap prevention.

### Audio QA Agent

Owns loudness, silence, clipping, track mix, and final media sanity.

### Linguistic QA Agent

Owns semantic faithfulness, named entities, numbers, and target-language quality.

### Test Engineer Agent

Owns focused test coverage and repeatable verification.

### Release Manager Agent

Owns versioning, changelog readiness, and git-flow hygiene.

## Milestone Comments

### Milestone: Core Architecture Scaffold

#### Product Owner Agent

- The scaffold follows the requested sequence: core first, CLI second, UI later.
- Root README had to be updated because the old copy described the product as an
  English-to-Russian script only.
- Next CLI milestone must expose source language, target language, translation
  mode, style, voice strategy, quality gate, and work directory.
- Acceptance for the next milestone should include a concrete `qa_report.json`
  contract, even if the first checks are minimal.

#### Analyst Agent

- Any-language translation is represented in config, but provider capabilities
  and fallback rules are not implemented yet.
- Modes, styles, and voice strategies are present as configuration values. The
  next milestones must map them to real rendering and voice-casting behavior.
- n8n is excluded from v1 runtime, but webhook preparation exists through docs
  and schema-versioned events.

#### Architect Agent

- The core package boundary is clean and independent from CLI/UI/media
  providers.
- The legacy `main.py` still owns the executable runtime and must be decomposed
  before the CLI becomes the main entrypoint.
- Project identity now uses one canonical value for `project.id` and
  `work_dir.name`.
- Artifact metadata now has typed records while keeping the simple artifact
  lookup map for compatibility.
- Stage/job foundation exists, but a real stage runner is still required before
  API/UI work.

#### Test Engineer Agent

- Focused tests cover config round trips, segment timing, project persistence,
  artifact records, and webhook events.
- Current verification command:
  `PYTHONPATH=src python3 -m unittest discover -s tests`.
- Syntax verification command:
  `python3 -m compileall -q src tests`.
- Keep using the standard-library test runner until the project intentionally
  adds a dev dependency manager.

#### Release Manager Agent

- Version remains `0.1.0` while the core model is being established.
- Branch follows the documented flow: `feature/core-architecture-scaffold` from
  `develop`.
- Python requirement is now consistently `3.11+`.
- Before merging to `develop`, rerun tests, syntax compilation, and
  `git diff --check`.

### Milestone: Core Pipeline Services

#### Product Owner Agent

- The milestone advances the requested order: core pipeline services are being
  built before CLI and UI.
- Mode, style, and voice strategy are still configuration-only. The next
  milestones must prove behavior for `voiceover`, `subtitles`, and one of
  `dub` or `dual_audio`.
- The autonomous path is closer because fake-provider stages can run without
  human review, but QA and retry policies are still future work.

#### Analyst Agent

- Provider contracts pass `PipelineConfig`, so any-language settings and style
  settings can flow into real providers later.
- Current stages cover extract, transcribe, translate, TTS, and render. Missing
  planned stages remain probe, speaker analysis, voice casting, timing fit, mix,
  QA, and export.
- Webhook readiness is still contract-level; stage event emission is expected in
  a later API/job milestone.

#### Architect Agent

- Pipeline services are provider-neutral and tested with fake providers.
- `PipelineRunner` now updates `VideoProject.status` to `running`, `completed`,
  or `failed`.
- `StageRun` records now include timestamps, inputs, outputs, and errors.
- Downstream stages enforce artifact preconditions before work.
- TTS output is registered as a typed artifact for resume/export inspection.

#### Test Engineer Agent

- Core tests were moved under `tests/unit` so the unit gate covers schema,
  store, webhook, runner, and version checks.
- Integration tests cover the fake-provider happy path and failure preconditions.
- E2E and load gates are runnable and currently contain gate-smoke tests.
- Current full verification:
  `PYTHONPATH=src python3 -m unittest discover -s tests`.

#### Release Manager Agent

- Version metadata is aligned at `0.2.0` in `VERSION`, `pyproject.toml`, and
  package `__version__`.
- `change.log` records `TVIDEO-002-core-pipeline-services`.
- Branch name follows the agreed `TVIDEO-XXX-short-name` format.
