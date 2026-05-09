# WebSocket Protocol — translateVideo

> Создан: 2026-05-09 | Версия: v1.97.0
> Источник: реальный код `src/translate_video/api/routes/projects.py:2111` + `ui/src/hooks/useProjectWebSocket.ts`

---

## Endpoint

```
ws://{host}/api/v1/projects/{project_id}/ws
```

**⚠️ Нет авторизации** (AP-WS-AUTH, P1 для R13). Любой знающий `project_id` может подключиться.

---

## Поведение (Backend)

```python
# projects.py:2111-2143
@router.websocket("/{project_id}/ws")
async def project_status_ws(websocket: WebSocket, project_id: str, store: ProjectStore):
    await websocket.accept()
    while True:
        project = store.load_project(...)
        payload = {
            "status": project.status,
            "progress_percent": getattr(project, "progress_percent", None),
            "eta_seconds": getattr(project, "eta_seconds", None),
        }
        await websocket.send_text(json.dumps(payload))
        if project.status not in ("running", "pending"):
            break  # сервер закрывает соединение когда завершено
        await asyncio.sleep(2)  # polling каждые 2 секунды
```

---

## Сообщения от сервера (server → client)

### Нормальный статус:
```json
{
  "status": "running",
  "progress_percent": 45.0,
  "eta_seconds": 120
}
```

### Ошибка — проект не найден:
```json
{
  "error": "not_found"
}
```

### Завершение (любой финальный статус):
```json
{
  "status": "completed",
  "progress_percent": 100.0,
  "eta_seconds": 0
}
```
*После этого сервер закрывает соединение.*

---

## Возможные значения `status`

| Статус | Описание | WS активен? |
|--------|----------|-------------|
| `created` | Создан, не запущен | Нет (Frontend не подключается) |
| `queued` | В очереди | Нет |
| `running` | Выполняется | **Да** |
| `pending` | Ожидает ресурсов | **Да** |
| `completed` | Завершён успешно | Нет (сервер закрыл) |
| `failed` | Ошибка | Нет (сервер закрыл) |
| `cancelled` | Отменён | Нет |

---

## Frontend реализация (TypeScript)

```typescript
// ui/src/hooks/useProjectWebSocket.ts
// WS URL автоматически переключается: dev (8002) vs prod (same host)
const WS_BASE = isViteDevServer
    ? "ws://localhost:8002/api/v1"
    : `${protocol === 'https:' ? 'wss' : 'ws'}://${host}/api/v1`;

// Тип сообщения
interface WSProjectStatus {
    status: string;
    progress_percent: number | null;
    eta_seconds: number | null;
    error?: string;
}
```

### Когда Frontend подключается:
- **Только** когда `status === 'running'` (параметр `enabled`)
- При `onclose` → вызывает `onDone()` → Dashboard делает финальный HTTP запрос
- При `onerror` → закрывает соединение (fallback на HTTP polling в `useProjectStatus.ts`)

### Нет сообщений от клиента к серверу
WebSocket используется только для получения обновлений (server push). Клиент ничего не отправляет.

---

## Lifecycle диаграмма

```
Client                          Server
  |                               |
  |── WS connect /{id}/ws ──────>|
  |                               | accept()
  |<── {status:"running", 45%} ──|  (через 0ms)
  |<── {status:"running", 67%} ──|  (через 2s)
  |<── {status:"running", 89%} ──|  (через 2s)
  |<── {status:"completed",100%}─|  (через 2s)
  |                               | close() ← сервер инициирует
  |── onclose → onDone() ────>   |
  |── HTTP GET /{id} ──────────>|  (финальный запрос)
```

---

## Известные ограничения (P1 → R13)

| # | Проблема | Решение |
|---|---------|---------|
| 1 | **Нет авторизации** (AP-WS-AUTH) | `api_key: str = Query(...)` + проверка settings |
| 2 | Backend использует `asyncio.sleep(2)` — это не push, а polling на сервере | Заменить на event-driven (asyncio.Event или Redis pub/sub) |
| 3 | Нет heartbeat/ping-pong | Клиент не знает об обрыве без данных |
| 4 | `project_id` в URL — UUID, но не проверяется ownership | Добавить проверку user/token |

---

## Тестирование

```bash
# Smoke тест — WS должен принять соединение и вернуть хотя бы 1 сообщение
python3 -c "
import asyncio, websockets, json

async def test():
    uri = 'ws://localhost:8002/api/v1/projects/test-fake-id/ws'
    try:
        async with websockets.connect(uri) as ws:
            msg = await asyncio.wait_for(ws.recv(), timeout=5)
            data = json.loads(msg)
            print('Received:', data)
    except Exception as e:
        print('Error:', e)

asyncio.run(test())
"
```

> Ожидаем: `{'error': 'not_found'}` для несуществующего project_id — это нормально.
> Ошибка: `ConnectionRefusedError` → сервер не запущен.
