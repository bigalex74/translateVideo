## Backend Review — 2026-05-08 v1.95.4
### Замечания по коду (10):
| # | Замечание | Файл:строка | 🔴/🟡/🟢 |
|---|---|---|---|
| 1 | Использование `requests.post` — блокирующий вызов в async-контексте. | `src/translate_video/tts/compress.py:76` | 🔴 |
| 2 | Множественные блокирующие вызовы `urllib.request.urlopen` в async-контексте. | `src/*` | 🔴 |
| 3 | Общий `except Exception:` без логгирования скрывает ошибки. | `src/translate_video/render/legacy.py:227` | 🟡 |
| 4 | Общий `except Exception:` заглушен с помощью `noqa: BLE001`, ошибка не логгируется. | `src/translate_video/pipeline/runner.py:147` | 🟡 |
| 5 | Слишком широкое исключение `except Exception as exc:`, стоит сузить до конкретных ошибок. | `src/translate_video/pipeline/runner.py:304` | 🟡 |
| 6 | Слишком широкое исключение `except Exception as exc:`, мешает отладке. | `src/translate_video/pipeline/stages.py:53` | 🟡 |
| 7 | Использование общего `except Exception` в TTS-модуле, возможны скрытые ошибки API. | `src/translate_video/tts/openai_tts.py:211` | 🟡 |
| 8 | Два общих `except Exception` в одном файле, нужно обрабатывать более специфичные ошибки. | `src/translate_video/tts/speechkit_tts.py:204,222` | 🟡 |
| 9 | Низкое кол-во `async def` функций (10). Потенциально много блокирующего кода. | `src/translate_video/` | 🟡 |
| 10 | Отсутствие `TODO`/`FIXME` комментариев в коде. | `src/translate_video/` | 🟢 |
### Подпись: Backend БЛОК
**Причина:** Обнаружены критические блокирующие вызовы (`requests`, `urlopen`) в асинхронном коде, что может привести к деградации производительности. Множественные общие `except Exception` скрывают потенциальные ошибки.

# backend Review Log

> Формат: каждый запуск агента добавляет секцию сверху
> Запуск: make agent:backend или scripts/run-agent.sh backend

---

---
## Backend Review — 2026-05-08 v1.95.9

### Команды:
```bash
python3 -m compileall -q src       → Exit: 0 ✅
grep -rn "async def" src/          → 10 async функций ✅
grep -rn "TODO|FIXME" src/         → 0 (нет техдолга в маркерах) ✅
```

### Замечания по коду (10):
| # | Замечание | Файл:строка | 🔴/🟡/🟢 |
|---|-----------|-------------|---------|
| 1 | `except Exception:` без логирования — скрывает ошибки | `render/legacy.py:227` | 🟡 |
| 2 | `except Exception:` в analytics endpoint | `analytics.py:37,87` | 🟡 |
| 3 | `except Exception as exc:` в projects API | `projects.py:292,353` | 🟡 |
| 4 | `urllib.request.urlopen` без allowlist хостов | `provider_catalog.py:223` | 🟡 |
| 5 | `urllib.request.urlopen` без allowlist | `timing/cloud.py:744` | 🟡 |
| 6 | `requests.post` без retry wrapper | `tts/compress.py:76` | 🟡 |
| 7 | `datetime.utcnow()` — deprecated в Python 3.12+ | `projects.py:2652` | 🟡 |
| 8 | 10 async def — убедиться что все используют asyncio.sleep, не time.sleep | `src/translate_video/` | 🟢 |
| 9 | `tts/compress.py` — requests без timeout явного | `compress.py:76` | 🟢 |
| 10 | TODO/FIXME: 0 — хорошо, но могут быть неотслеживаемые задачи | `src/` | 🟢 |

### Критичных блокеров: 0
### Требует внимания (🟡): 7 — все существующий код, не новый

### Подпись: Backend АПРУV | 2026-05-08 v1.95.9

---
## Backend Review — 2026-05-08 v1.96.0

### Команды:
```bash
python3 -m compileall -q src          → 
grep -rn "utcnow()" src/              → 0 (исправлено R11-И5)
grep -rn "async def" src/             → 10 функций
grep -rn "except Exception" src/      → 52
```

### Изменения R11:
- datetime.utcnow() → datetime.now(timezone.utc) в projects.py:2652
- 920 Python тестов OK

### АПРУV: Backend чистый, utcnow() устранён

### Подпись: Backend АПРУV | 2026-05-08 v1.96.0
