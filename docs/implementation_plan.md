# Архивный План TVIDEO-008: Валидация И Укрепление Базовой Функциональности

> Документ сохранён как исторический план этапа TVIDEO-008. Большая часть
> пунктов уже реализована в последующих версиях. Актуальную дорожную карту
> смотрите в `docs/wiki/roadmap.md`, актуальный релизный gate — в
> `docs/testing-strategy.md` и `Makefile`.

Перед переходом к UI (0.7.0 roadmap) необходимо убедиться, что вся базовая
функциональность ядра, CLI и экспорта работает надёжно. Этот этап закрывает
выявленные пробелы и добавляет защитные тесты.

## User Review Required

> [!IMPORTANT]
> Этот этап **не добавляет нового функционала** — только укрепляет существующий.
> Версия останется `0.7.x` (PATCH-бамп). Если нужен новый функционал до UI —
> лучше выделить отдельный этап.

> [!WARNING]
> Найден и уже починен баг: `__init__.py.__version__` не был обновлён при
> bump до 0.7.0. Тест `test_version_files_are_aligned` падал бы.
> Фикс закоммичен в `develop`.

## Выявленные Пробелы

По результатам анализа всех 98 тестов и исходного кода выявлены следующие зоны риска:

| # | Пробел | Риск | Файлы |
|---|--------|------|-------|
| 1 | **PipelineRunner** — только 1 тест (fail-stop), нет теста успешного завершения и пустого пайплайна | Средний | runner.py, test_pipeline_runner.py |
| 2 | **Возобновление проекта** — `run --work-dir` перезапускает все этапы с нуля, нет пропуска завершённых | Высокий | runner.py, stages.py |
| 3 | **CLI error handling** — `main()` не ловит исключения, падает с traceback в stderr | Средний | cli.py |
| 4 | **Config валидация** — нет проверки пустых/невалидных language codes, config принимает любые строки | Низкий | config.py |
| 5 | **Segment граничные случаи** — нет тестов: unicode в тексте, пустой source_text, 0-длительность, перекрытие таймингов | Средний | schemas.py, test_core_schemas.py |
| 6 | **Store идемпотентность** — `add_artifact` заменяет по kind, но нет теста повторной записи segments | Низкий | store.py, test_core_store.py |
| 7 | **Export edge cases** — нет тестов: многострочный текст в SRT, спецсимволы, пустой список сегментов (для srt/vtt) | Средний | srt.py, vtt.py |
| 8 | **Нагрузочные тесты** — только заглушка `test_load_gate.py`, нет реальной проверки параллельных проектов | Низкий | tests/load/ |
| 9 | **Coverage** — не настроен, нет отчёта о покрытии | Средний | — |
| 10 | **Версия в 3 местах** — при bump нужно менять VERSION, pyproject.toml, __init__.py вручную | Низкий | — |

## Proposed Changes

### Компонент 1: Покрытие кода (coverage)

Настроить `coverage` для измерения покрытия и выявления слепых зон.

#### [MODIFY] [pyproject.toml](file:///home/user/translateVideo/pyproject.toml)
- Добавить `coverage` в `[project.optional-dependencies] dev`
- Добавить секцию `[tool.coverage.run]` и `[tool.coverage.report]`

---

### Компонент 2: PipelineRunner — дополнительные тесты

#### [MODIFY] [test_pipeline_runner.py](file:///home/user/translateVideo/tests/unit/test_pipeline_runner.py)
- Тест успешного завершения всех этапов → статус `COMPLETED`
- Тест пустого списка этапов → статус `COMPLETED` без запусков
- Тест: при ошибке этапа последующие этапы не вызываются

---

### Компонент 3: Возобновление пайплайна (skip completed)

Добавить логику пропуска завершённых этапов при `run --work-dir`.

#### [MODIFY] [runner.py](file:///home/user/translateVideo/src/translate_video/pipeline/runner.py)
- Добавить проверку: если `project.stage_runs` содержит `COMPLETED` запись
  для данного `stage`, пропустить этап и вернуть `StageRun` со статусом `SKIPPED`
- Добавить параметр `force: bool = False` для принудительного перезапуска

#### [MODIFY] [cli.py](file:///home/user/translateVideo/src/translate_video/cli.py)
- Добавить флаг `--force` к команде `run`

#### [MODIFY] [test_pipeline_runner.py](file:///home/user/translateVideo/tests/unit/test_pipeline_runner.py)
- Тест: ранее завершённый этап пропускается
- Тест: `--force` заставляет перезапустить завершённый этап

#### [NEW] [test_resume.py](file:///home/user/translateVideo/tests/integration/test_resume.py)
- Интеграционный тест: прогнать пайплайн, загрузить проект, прогнать снова → этапы пропущены

---

### Компонент 4: CLI error handling

#### [MODIFY] [cli.py](file:///home/user/translateVideo/src/translate_video/cli.py)
- Обернуть `main()` в try/except для `FileNotFoundError`, `ValueError`,
  `json.JSONDecodeError` — вывод человеко-читаемой ошибки вместо traceback
- Возвращать ненулевой exit code при ошибках

#### [MODIFY] [test_cli.py](file:///home/user/translateVideo/tests/unit/test_cli.py)
- Тест: несуществующий `--work-dir` → ошибка без traceback
- Тест: повреждённый `project.json` → ошибка без traceback

---

### Компонент 5: Segment и Schema edge cases

#### [MODIFY] [test_core_schemas.py](file:///home/user/translateVideo/tests/unit/test_core_schemas.py)
- Тест: сегмент с пустым `source_text`
- Тест: сегмент с нулевой длительностью (`start == end`)
- Тест: сегмент с unicode (кириллица, emoji, CJK)
- Тест: `VideoProject.from_dict` → `to_dict` roundtrip
- Тест: `StageRun.from_dict` с минимальным payload (только обязательные поля)

---

### Компонент 6: Store robustness

#### [MODIFY] [test_core_store.py](file:///home/user/translateVideo/tests/unit/test_core_store.py)
- Тест: повторный `save_segments` (translated=True) заменяет предыдущий артефакт
- Тест: `export_subtitles` с пустым списком сегментов
- Тест: `load_project` несуществующей папки → `FileNotFoundError`
- Тест: `export_subtitles` с невалидным форматом → `ValueError`

---

### Компонент 7: Export edge cases

#### [MODIFY] [test_export_srt.py](file:///home/user/translateVideo/tests/unit/test_export_srt.py)
- Тест: многострочный текст в сегменте
- Тест: спецсимволы `<`, `>`, `&` в тексте
- Тест: пустой список сегментов → пустая строка

#### [MODIFY] [test_export_vtt.py](file:///home/user/translateVideo/tests/unit/test_export_vtt.py)
- Аналогичные edge case тесты для VTT

#### [MODIFY] [test_timing_report.py](file:///home/user/translateVideo/tests/unit/test_timing_report.py)
- Тест: сегмент с нулевой длительностью (деление на ноль в chars_per_sec)

---

### Компонент 8: Нагрузочный тест параллельных проектов

#### [MODIFY] [test_load_gate.py](file:///home/user/translateVideo/tests/load/test_load_gate.py)
- Тест: создание 20 проектов параллельно (ThreadPoolExecutor)
- Тест: запуск fake-пайплайна на 10 проектах подряд, проверка изоляции артефактов

---

### Компонент 9: Скрипт синхронизации версий

#### [NEW] [scripts/bump_version.py](file:///home/user/translateVideo/scripts/bump_version.py)
- Единая точка обновления VERSION, pyproject.toml, __init__.py
- `python3 scripts/bump_version.py 0.7.1`

---

## Verification Plan

### Automated Tests

```bash
# Полный прогон (должно быть ~120+ тестов)
PYTHONPATH=src python3 -m unittest discover -s tests

# Coverage-отчёт
PYTHONPATH=src python3 -m coverage run -m unittest discover -s tests
python3 -m coverage report --show-missing

# Синтаксис
python3 -m compileall -q src tests
```

### Manual Verification

- Запуск `run --work-dir` на ранее завершённом проекте → этапы должны быть `SKIPPED`
- Запуск `run --work-dir --force` → этапы должны перезапуститься
- Подача несуществующего файла в CLI → человеко-читаемая ошибка, exit code 1
- `python3 scripts/bump_version.py 0.7.1` → все 3 файла обновлены

## Open Questions

> [!IMPORTANT]
> **Минимальный порог coverage**: Какой % покрытия считать приемлемым для перехода
> к UI? Предлагаю 80% строк для `src/translate_video/`.

> [!NOTE]
> **Возобновление пайплайна**: Пропуск этапов реализуется по наличию `COMPLETED`
> записи в `stage_runs`. Если данные артефакта изменились (например, пользователь
> отредактировал transcript.translated.json), нужно ли инвалидировать последующие
> этапы? Предлагаю в этом этапе НЕ реализовывать инвалидацию — только простой
> пропуск. Инвалидацию отложить до UI, где редактирование артефактов станет
> реальным сценарием.
