# ml-engineer Review Log

> Формат: каждый запуск агента добавляет секцию сверху
> Запуск: make agent:ml-engineer или scripts/run-agent.sh ml-engineer

---

---
## ML Engineer Review — 2026-05-08 v1.95.9

### Команды:
```bash
grep -rn "openai\|whisper\|deepseek\|model" src/translate_video/translation/ | head -10
grep -rn "billing_snapshots\|cost_usd" src/translate_video/ | grep -v "__pycache__" | head -5
```

### Замечания (10):
| # | Замечание | Файл:строка | 🔴/🟡/🟢 |
|---|-----------|-------------|---------|
| 1 | **billing_snapshots**: стоимость LLM-вызовов сохраняется — основа для оптимизации промптов по цене ✅ | `schemas.py` | 🟢 |
| 2 | **Глоссарий для всех**: правильно — качество перевода улучшается от пользовательских терминов | `Settings` | 🟢 |
| 3 | **Batch processing**: параллельная обработка нескольких видео — нужно убедиться в rate limit handling | `pipeline.py` | 🟡 |
| 4 | **DOCX export**: перевод сохраняется корректно (source_text + translated_text) ✅ | `projects.py:1681` | 🟢 |
| 5 | **TTS качество**: openai_tts.py (474 строк) и speechkit_tts.py — мониторинг качества не добавлен | `tts/` | 🟡 |
| 6 | **Retry механизм**: with_retry используется в основных LLM вызовах ✅ | `src/` | 🟢 |
| 7 | **Стоимость видна пользователю**: первый шаг к прозрачному billing ✅ | `Dashboard` | 🟢 |
| 8 | **Оценка качества**: stats-quality-gauge есть в UI. Метрика правильная? Нужен WER/BLEU | `StatsPanel` | 🟡 |
| 9 | **Whisper model size**: какой используется? tiny/small/large влияет на cost/quality tradeoff | `transcribe/` | 🟡 |
| 10 | **GPU утилизация**: docker stats показывает 3% CPU — GPU не используется? Для whisper критично | `Dockerfile` | 🟡 |

### Подпись: ML Engineer АПРУV | 2026-05-08 v1.95.9
