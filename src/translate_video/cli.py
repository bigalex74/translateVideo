"""CLI-обертка над ядром перевода видео."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import TextIO

from translate_video.core.config import (
    AdaptationLevel,
    PipelineConfig,
    QualityGate,
    TranslationMode,
    TranslationStyle,
    VoiceStrategy,
)
from translate_video.core.schemas import Segment
from translate_video.core.store import ProjectStore
from translate_video.pipeline import (
    ExtractAudioStage,
    PipelineRunner,
    RenderStage,
    StageContext,
    TTSStage,
    TranscribeStage,
    TranslateStage,
)


def main(argv: list[str] | None = None, stdout: TextIO | None = None) -> int:
    """Выполнить CLI-команду и вернуть код завершения."""

    output = stdout or sys.stdout
    parser = build_parser()
    args = parser.parse_args(argv)
    result = args.handler(args)
    if result is not None:
        print(json.dumps(result, ensure_ascii=False, indent=2), file=output)
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Создать парсер команд CLI."""

    parser = argparse.ArgumentParser(
        prog="translate-video",
        description="Управление проектами ИИ-перевода видео.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="создать проект без запуска пайплайна")
    _add_project_creation_arguments(init_parser)
    init_parser.set_defaults(handler=_handle_init)

    run_parser = subparsers.add_parser("run", help="создать или загрузить проект и выполнить пайплайн")
    run_parser.add_argument("input_video", nargs="?", help="путь к исходному видео")
    run_parser.add_argument("--work-dir", type=Path, help="папка ранее созданного проекта")
    _add_config_arguments(run_parser)
    run_parser.add_argument("--work-root", type=Path, default=Path("runs"), help="корень рабочих папок")
    run_parser.add_argument("--project-id", help="явный идентификатор нового проекта")
    run_parser.add_argument(
        "--provider",
        choices=["fake"],
        default="fake",
        help="набор провайдеров для запуска; реальные адаптеры появятся отдельной веткой",
    )
    run_parser.set_defaults(handler=_handle_run)

    status_parser = subparsers.add_parser("status", help="показать статус проекта")
    status_parser.add_argument("work_dir", type=Path, help="папка проекта")
    status_parser.set_defaults(handler=_handle_status)

    artifacts_parser = subparsers.add_parser("artifacts", help="показать артефакты проекта")
    artifacts_parser.add_argument("work_dir", type=Path, help="папка проекта")
    artifacts_parser.set_defaults(handler=_handle_artifacts)

    config_parser = subparsers.add_parser("config", help="показать настройки проекта")
    config_parser.add_argument("work_dir", type=Path, help="папка проекта")
    config_parser.set_defaults(handler=_handle_config)

    return parser


def _add_project_creation_arguments(parser: argparse.ArgumentParser) -> None:
    """Добавить аргументы создания проекта."""

    parser.add_argument("input_video", help="путь к исходному видео")
    parser.add_argument("--work-root", type=Path, default=Path("runs"), help="корень рабочих папок")
    parser.add_argument("--project-id", help="явный идентификатор проекта")
    _add_config_arguments(parser)


def _add_config_arguments(parser: argparse.ArgumentParser) -> None:
    """Добавить общие аргументы конфигурации пайплайна."""

    parser.add_argument("--source-language", default="auto", help="код исходного языка или auto")
    parser.add_argument("--target-language", default="ru", help="код целевого языка")
    parser.add_argument("--translation-mode", choices=_values(TranslationMode), default=TranslationMode.VOICEOVER)
    parser.add_argument("--translation-style", choices=_values(TranslationStyle), default=TranslationStyle.NEUTRAL)
    parser.add_argument("--adaptation-level", choices=_values(AdaptationLevel), default=AdaptationLevel.NATURAL)
    parser.add_argument("--voice-strategy", choices=_values(VoiceStrategy), default=VoiceStrategy.SINGLE)
    parser.add_argument("--quality-gate", choices=_values(QualityGate), default=QualityGate.BALANCED)
    parser.add_argument("--terminology-domain", default="general", help="предметная область терминов")
    parser.add_argument("--target-audience", default="general", help="целевая аудитория")
    parser.add_argument("--glossary-path", type=Path, help="путь к глоссарию")
    parser.add_argument(
        "--do-not-translate",
        action="append",
        default=[],
        help="термин, который нельзя переводить; можно указать несколько раз",
    )


def _handle_init(args: argparse.Namespace) -> dict:
    """Создать проект и вернуть его краткое описание."""

    store = ProjectStore(args.work_root)
    project = store.create_project(
        input_video=args.input_video,
        config=_config_from_args(args),
        project_id=args.project_id,
    )
    return _project_summary(project)


def _handle_run(args: argparse.Namespace) -> dict:
    """Запустить пайплайн для нового или существующего проекта."""

    store = ProjectStore(args.work_root)
    if args.work_dir:
        project = store.load_project(args.work_dir)
    elif args.input_video:
        project = store.create_project(
            input_video=args.input_video,
            config=_config_from_args(args),
            project_id=args.project_id,
        )
    else:
        raise SystemExit("для run укажите input_video или --work-dir")

    runner = PipelineRunner(_build_stages(args.provider))
    runs = runner.run(StageContext(project=project, store=store))
    restored = store.load_project(project.work_dir)
    summary = _project_summary(restored)
    summary["runs"] = [run.to_dict() for run in runs]
    return summary


def _handle_status(args: argparse.Namespace) -> dict:
    """Вернуть статус проекта."""

    project = ProjectStore(args.work_dir.parent).load_project(args.work_dir)
    summary = _project_summary(project)
    summary["stage_runs"] = [run.to_dict() for run in project.stage_runs]
    return summary


def _handle_artifacts(args: argparse.Namespace) -> dict:
    """Вернуть список артефактов проекта."""

    project = ProjectStore(args.work_dir.parent).load_project(args.work_dir)
    return {
        "project_id": project.id,
        "work_dir": project.work_dir.as_posix(),
        "artifacts": [record.to_dict() for record in project.artifact_records],
    }


def _handle_config(args: argparse.Namespace) -> dict:
    """Вернуть сохраненную конфигурацию проекта."""

    project = ProjectStore(args.work_dir.parent).load_project(args.work_dir)
    return project.config.to_dict()


def _config_from_args(args: argparse.Namespace) -> PipelineConfig:
    """Собрать конфигурацию пайплайна из CLI-аргументов."""

    return PipelineConfig(
        source_language=args.source_language,
        target_language=args.target_language,
        translation_mode=TranslationMode(args.translation_mode),
        translation_style=TranslationStyle(args.translation_style),
        adaptation_level=AdaptationLevel(args.adaptation_level),
        voice_strategy=VoiceStrategy(args.voice_strategy),
        quality_gate=QualityGate(args.quality_gate),
        terminology_domain=args.terminology_domain,
        target_audience=args.target_audience,
        glossary_path=args.glossary_path,
        do_not_translate=list(args.do_not_translate),
    )


def _build_stages(provider: str):
    """Создать этапы пайплайна для выбранного набора провайдеров."""

    if provider != "fake":
        raise ValueError(f"неподдерживаемый провайдер CLI: {provider}")
    return [
        ExtractAudioStage(FakeMediaProvider()),
        TranscribeStage(FakeTranscriber()),
        TranslateStage(FakeTranslator()),
        TTSStage(FakeTTSProvider()),
        RenderStage(FakeRenderer()),
    ]


def _project_summary(project) -> dict:
    """Вернуть короткое JSON-представление проекта для CLI."""

    return {
        "project_id": project.id,
        "status": project.status,
        "input_video": project.input_video.as_posix(),
        "work_dir": project.work_dir.as_posix(),
        "segments": len(project.segments),
        "artifacts": dict(project.artifacts),
    }


def _values(enum_type) -> list[str]:
    """Вернуть строковые значения enum для argparse choices."""

    return [item.value for item in enum_type]


class FakeMediaProvider:
    """Имитационный медиа-провайдер для проверки CLI без внешних зависимостей."""

    def extract_audio(self, project):
        """Создать минимальный аудио-артефакт."""

        output = project.work_dir / "source_audio.wav"
        output.write_bytes(b"fake audio")
        return output


class FakeTranscriber:
    """Имитационный распознаватель для CLI smoke-сценариев."""

    def transcribe(self, audio_path, config):
        """Вернуть один сегмент без обращения к внешним моделям."""

        return [Segment(id="seg_1", start=0.0, end=1.0, source_text="Пример речи")]


class FakeTranslator:
    """Имитационный переводчик, сохраняющий детерминированное поведение CLI."""

    def translate(self, segments, config):
        """Вернуть сегменты с текстом, помеченным целевым языком."""

        return [
            Segment(
                id=segment.id,
                start=segment.start,
                end=segment.end,
                source_text=segment.source_text,
                translated_text=f"{config.target_language}: {segment.source_text}",
            )
            for segment in segments
        ]


class FakeTTSProvider:
    """Имитационный TTS-провайдер для создания локальных аудио-файлов."""

    def synthesize(self, project, segments):
        """Записать минимальные TTS-файлы и обновить пути сегментов."""

        for segment in segments:
            tts_path = project.work_dir / "tts" / f"{segment.id}.wav"
            tts_path.write_bytes(b"fake speech")
            segment.tts_path = tts_path.relative_to(project.work_dir).as_posix()
        return segments


class FakeRenderer:
    """Имитационный рендерер для создания итогового видео-артефакта."""

    def render(self, project, segments):
        """Записать минимальный итоговый файл."""

        output = project.work_dir / "output" / "translated.mp4"
        output.write_bytes(b"fake video")
        return output


if __name__ == "__main__":
    raise SystemExit(main())
