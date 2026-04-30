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

В репозитории пока остается исходный прототип `main.py`. Он умеет
извлекать аудио, распознавать речь через `faster-whisper`, переводить текст
через `deep-translator`, генерировать русскую речь через `edge-tts` и собирать
видео с закадровой озвучкой.

Новая разработка ведется в `src/translate_video/`:

- языконезависимая конфигурация пайплайна;
- типизированные схемы проекта, сегментов, артефактов, этапов и webhook;
- хранилище артефактов для каждого проекта;
- провайдер-независимый раннер пайплайна;
- CLI-команды для создания, запуска и просмотра проектов.

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

Пока CLI использует имитационные провайдеры, чтобы проверять ядро без внешних
моделей и тяжелой обработки медиа. Реальные адаптеры добавляются отдельно.

```bash
PYTHONPATH=src python3 -m translate_video.cli init "path/to/video.mp4" \
  --project-id demo \
  --source-language en \
  --target-language ru

PYTHONPATH=src python3 -m translate_video.cli run --work-dir runs/demo
PYTHONPATH=src python3 -m translate_video.cli status runs/demo
PYTHONPATH=src python3 -m translate_video.cli artifacts runs/demo
PYTHONPATH=src python3 -m translate_video.cli config runs/demo
```

## Тесты

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
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
- `docs/webhooks.md`
- `docs/wiki/roadmap.md`
