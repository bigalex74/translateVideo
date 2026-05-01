# AI Video Translator

AI Video Translator развивается из одного Python-скрипта в переиспользуемый
движок перевода видео. Целевой продукт переводит видео с любого поддерживаемого
исходного языка на любой поддерживаемый целевой язык, а затем экспортирует
закадровую озвучку, дубляж, субтитры или видео с несколькими аудиодорожками.

Порядок разработки:

1. Ядро.
2. CLI.
3. Локальный UI.
4. API/webhook-слой для внешних оркестраторов, например n8n.

## Текущее Состояние

В репозитории остается исходный прототип `main.py`, но основная разработка уже
ведется в переиспользуемом пакете `src/translate_video/`, CLI, FastAPI API и
React/Vite UI.

Реализовано:

- языконезависимая конфигурация пайплайна;
- типизированные схемы проекта, сегментов, артефактов, этапов и webhook;
- хранилище артефактов для каждого проекта;
- провайдер-независимый раннер пайплайна;
- CLI-команды для предварительной проверки, создания, запуска и просмотра
- FastAPI API для проектов, загрузки файлов, запуска пайплайна, артефактов и
  webhook-уведомлений;
- UI с дашбордом, wizard создания проекта, workspace-редактором, видеоплеером,
  QA-сводкой и переключением языка `ru/en`;
- browser E2E на мокированном API и fullstack browser E2E против реального
  FastAPI backend.

## Планируемые Возможности

- Исходный язык: `auto` или явный код языка.
- Целевой язык: любой код языка, поддерживаемый выбранным провайдером.
- Режимы перевода: `voiceover`, `dub`, `subtitles`, `dual_audio`, `learning`.
- Стили перевода: `neutral`, `business`, `casual`, `humorous`,
  `educational`, `cinematic`, `child_friendly`.
- Стратегии голосов: один голос, два голоса, по полу или отдельный голос для
  каждого спикера.
- Автоматическая QA-проверка: тайминги, глоссарий, смысл, аудио, рендер и язык.
- Будущая интеграция с n8n через API/webhook-границу.

## Требования

- Python 3.11+
- FFmpeg доступен в `PATH`

## Установка

```bash
git clone https://github.com/bigalex74/translateVideo.git
cd translateVideo
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Использование Устаревшего Скрипта

```bash
python3 main.py "path/to/video.mp4"
```

Устаревший скрипт записывает `translated_<input-name>` рядом с исходным видео.
Позже эта точка входа станет тонким CLI-адаптером поверх нового ядра.

## Использование CLI

По умолчанию CLI использует имитационные провайдеры, чтобы проверять ядро без
внешних моделей и тяжелой обработки медиа. Для запуска через адаптеры
устаревшего скрипта используйте `--provider legacy`.

```bash
PYTHONPATH=src python3 -m translate_video.cli preflight "path/to/video.mp4" \
  --provider legacy

PYTHONPATH=src python3 -m translate_video.cli init "path/to/video.mp4" \
  --project-id demo \
  --source-language en \
  --target-language ru

PYTHONPATH=src python3 -m translate_video.cli run --work-dir runs/demo
PYTHONPATH=src python3 -m translate_video.cli run --work-dir runs/demo --provider legacy
PYTHONPATH=src python3 -m translate_video.cli status runs/demo
PYTHONPATH=src python3 -m translate_video.cli artifacts runs/demo
PYTHONPATH=src python3 -m translate_video.cli config runs/demo
```

## Тесты

```bash
make test:release
```

## Структура Репозитория

- `main.py`: устаревший прототип пайплайна.
- `src/translate_video/`: переиспользуемый пакет в активной разработке.
- `src/translate_video/cli.py`: CLI-адаптер поверх ядра.
- `tests/`: сфокусированные тесты изменяемого поведения.
- `docs/`: архитектура, процесс разработки, webhook-план и wiki.
- `requirements.txt`: зависимости устаревшего скрипта.
- `pyproject.toml`: метаданные пакета и версия.

## Документация

Начинать лучше отсюда:

- `docs/architecture.md`
- `docs/development-process.md`
- `docs/testing-strategy.md`
- `docs/manual-testing.md`
- `docs/webhooks.md`
- `docs/wiki/roadmap.md`
