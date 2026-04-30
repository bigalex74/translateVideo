# AI Video Translator

AI Video Translator is evolving from a single Python script into a reusable video
translation engine. The target product translates videos from any supported
source language into any supported target language, then exports voiceover,
dubbed audio, subtitles, or dual-audio media.

The project is being developed in this order:

1. Core engine.
2. CLI.
3. Local UI.
4. API/webhooks for external orchestrators such as n8n.

## Current State

The repository still includes the original `main.py` proof of concept. It can
extract audio, transcribe speech with `faster-whisper`, translate text with
`deep-translator`, generate Russian speech with `edge-tts`, and render a
voiceover video.

The new work starts under `src/translate_video/`:

- language-agnostic pipeline configuration;
- typed project, segment, artifact, stage, and webhook schemas;
- per-project artifact store;
- tests for the core contracts.

## Planned Capabilities

- Source language: `auto` or explicit language code.
- Target language: any provider-supported language code.
- Translation modes: `voiceover`, `dub`, `subtitles`, `dual_audio`, `learning`.
- Translation styles: `neutral`, `business`, `casual`, `humorous`,
  `educational`, `cinematic`, `child_friendly`.
- Voice strategies: single voice, two voices, by gender, or per speaker.
- Autonomous QA: timing, glossary, semantic, audio, render, and language checks.
- Future n8n integration through a webhook/API boundary.

## Requirements

- Python 3.11+
- FFmpeg available in `PATH`

## Install

```bash
git clone https://github.com/bigalex74/translateVideo.git
cd translateVideo
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Legacy Script Usage

```bash
python3 main.py "path/to/video.mp4"
```

The legacy script writes `translated_<input-name>` next to the input video. This
entrypoint will later become a thin CLI adapter over the new core package.

## Tests

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```

## Repository Structure

- `main.py`: legacy proof-of-concept pipeline.
- `src/translate_video/`: reusable package under active development.
- `tests/`: focused unit tests for changed behavior.
- `docs/`: architecture, development process, webhook plan, and wiki notes.
- `requirements.txt`: runtime dependencies for the legacy script.
- `pyproject.toml`: package metadata and version.

## Documentation

Start with:

- `docs/architecture.md`
- `docs/development-process.md`
- `docs/webhooks.md`
- `docs/wiki/roadmap.md`
