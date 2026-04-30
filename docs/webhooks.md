# План Webhook-И API-Интеграции

## Область

n8n не входит в процесс исполнения первой версии. Первая версия держит оркестрацию в
Python, но заранее резервирует API/webhook-границу для будущей автоматизации.

## Будущая Схема Интеграции

```text
n8n
  -> POST /api/projects
  -> POST /api/projects/{id}/jobs
  -> GET /api/jobs/{id}
  -> GET /api/projects/{id}/artifacts
  -> получает webhook-события
```

## Планируемые События

```json
{
  "event": "job.stage.completed",
  "project_id": "example",
  "job_id": "job_123",
  "stage": "translate",
  "status": "completed",
  "artifact_path": "transcript.translated.json"
}
```

События для будущей поддержки:

- `project.created`
- `job.started`
- `job.stage.started`
- `job.stage.completed`
- `job.stage.failed`
- `qa.completed`
- `render.completed`

## Ограничения Дизайна

- Данные webhook должны быть JSON-сериализуемыми и иметь версию схемы.
- Данные webhook должны содержать идентификаторы, статус, этап и ссылки на
  артефакты.
- Внешние оркестраторы не должны иметь доступ к внутренним Python-объектам.
- API-клиент должен иметь возможность продолжить или перезапустить упавший этап.
