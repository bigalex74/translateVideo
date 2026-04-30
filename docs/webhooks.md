# Webhook and n8n Integration Plan

## Scope

n8n is not part of the first runtime. The first version keeps orchestration in
Python, while reserving an API/webhook boundary for future automation.

## Future Integration Shape

```text
n8n
  -> POST /api/projects
  -> POST /api/projects/{id}/jobs
  -> GET /api/jobs/{id}
  -> GET /api/projects/{id}/artifacts
  -> receive webhook events
```

## Planned Events

```json
{
  "event": "job.stage.completed",
  "project_id": "example",
  "job_id": "job_123",
  "stage": "translation",
  "status": "completed",
  "artifact_path": "transcript.translated.json"
}
```

Events to support later:

- `project.created`
- `job.started`
- `job.stage.started`
- `job.stage.completed`
- `job.stage.failed`
- `qa.completed`
- `render.completed`

## Design Constraints

- Webhook payloads must be JSON-serializable and schema-versioned.
- Payloads must contain IDs, status, stage, and artifact references.
- External orchestrators should never need direct access to internal Python
  objects.
- API callers should be able to resume or rerun a failed stage.
