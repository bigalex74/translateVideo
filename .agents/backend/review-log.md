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
