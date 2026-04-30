# Roadmap

## 0.1.0 Core Model

- Package structure.
- Project and segment schemas.
- Artifact store.
- Pipeline configuration.
- Focused unit tests.

## 0.2.0 Core Pipeline Services

- Provider interfaces for media, speech, translation, TTS, and render.
- Sequential pipeline runner.
- Fake-provider integration path.
- Stage run and artifact recording.

## 0.3.0 CLI

- `translate-video` entrypoint.
- Run current pipeline through the new core.
- Per-video work directories.
- Resume support.

## 0.4.0 Editable Artifacts

- Import/export JSON.
- SRT/VTT export.
- Translation review artifact.
- Timing report.

## 0.5.0 Local UI

- Project list.
- Upload/select input video.
- Settings form.
- Segment table.
- Render and download artifacts.

## 0.6.0 API and Webhooks

- Local REST API.
- Job status.
- Webhook event schemas.
- n8n integration examples.
