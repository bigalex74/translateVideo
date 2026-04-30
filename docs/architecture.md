# Architecture

## Direction

The project is becoming a reusable AI video translation engine with three public
surfaces built in this order:

1. Core Python package.
2. CLI on top of the core.
3. UI on top of the same core and job API.

The first version keeps n8n outside the runtime, but the system must expose a
stable webhook/API boundary so n8n can orchestrate jobs later.

## Core Principles

- The core owns all business logic. CLI and UI only call core services.
- Every long-running step writes artifacts to a project directory.
- Translation is language-agnostic: any source language can target any supported
  destination language.
- Each stage is independently rerunnable.
- Tests cover the code that changes in the same milestone.
- Human review is optional, not required by the default flow.

## Pipeline

```text
Input video
  -> project initialization
  -> media probe
  -> audio extraction
  -> transcription
  -> speaker analysis
  -> translation planning
  -> translation and adaptation
  -> voice casting
  -> TTS generation
  -> timing fit
  -> audio mix
  -> render
  -> automated QA
  -> export
```

## Translation Modes

- `voiceover`: translated speech over a lowered original track.
- `dub`: translated speech replaces the original speech track.
- `subtitles`: translated subtitles only.
- `dual_audio`: final media keeps both original and translated audio tracks.
- `learning`: keeps original audio and adds translated subtitles plus learning
  metadata where available.

## Translation Style

Style is a first-class configuration option, not a prompt afterthought:

- `neutral`
- `business`
- `casual`
- `humorous`
- `educational`
- `cinematic`
- `child_friendly`

The engine also tracks adaptation level, terminology domain, glossary, audience,
profanity policy, unit conversion policy, and do-not-translate terms.

## Artifact Layout

```text
runs/
  <project-id>/
    project.json
    settings.json
    source_audio.wav
    transcript.source.json
    transcript.translated.json
    speakers.json
    subtitles/
    tts/
    output/
    qa_report.json
```

## Package Layout

```text
src/translate_video/
  core/
  media/
  speech/
  translation/
  tts/
  render/
  quality/
  agents/
  api/
  cli.py
```

## Agent Model

Agents are typed services with strict inputs and outputs. They do not replace
deterministic pipeline code. The manager can ask agents to retry or improve a
stage, but artifacts remain the source of truth.

Initial roles:

- Product Owner Agent
- Analyst Agent
- Architect Agent
- Translation Agent
- Timing Agent
- Audio QA Agent
- Linguistic QA Agent
- Test Engineer Agent
- Release Manager Agent

## Quality Gates

The QA system combines deterministic checks and AI-based review:

- media file opens and has expected duration;
- audio exists and is not silent;
- translated language matches the target;
- required glossary terms are present;
- named entities, numbers, and dates survive translation;
- generated speech fits segment timing;
- final render includes expected tracks and subtitles;
- QA score meets the selected quality gate.
