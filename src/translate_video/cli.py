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
from translate_video.core.preflight import run_preflight
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
    build_stages as _build_stages_impl,
    project_summary as _project_summary_impl,
)


def main(argv: list[str] | None = None, stdout: TextIO | None = None) -> int:
    """Выполнить CLI-команду и вернуть код завершения."""

    output = stdout or sys.stdout
    parser = build_parser()
    
    try:
        args = parser.parse_args(argv)
        result = args.handler(args)
        if result is not None:
            print(json.dumps(result, ensure_ascii=False, indent=2), file=output)
        return 0
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as err:
        print(f"Ошибка: {err}", file=sys.stderr)
        return 1
    except SystemExit as err:
        if isinstance(err.code, str):
            print(f"Ошибка: {err.code}", file=sys.stderr)
            return 1
        return err.code or 0


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
    run_parser.add_argument("--force", action="store_true", help="принудительно перезапустить завершенные этапы")
    _add_config_arguments(run_parser)
    run_parser.add_argument("--work-root", type=Path, default=Path("runs"), help="корень рабочих папок")
    run_parser.add_argument("--project-id", help="явный идентификатор нового проекта")
    run_parser.add_argument(
        "--provider",
        choices=["fake", "legacy"],
        default="fake",
        help="набор провайдеров для запуска",
    )
    run_parser.set_defaults(handler=_handle_run)

    preflight_parser = subparsers.add_parser(
        "preflight",
        help="проверить файл и окружение без запуска перевода",
    )
    preflight_parser.add_argument("input_video", type=Path, help="путь к исходному видео")
    preflight_parser.add_argument(
        "--provider",
        choices=["fake", "legacy"],
        default="legacy",
        help="набор провайдеров, готовность которого нужно проверить",
    )
    preflight_parser.set_defaults(handler=_handle_preflight)

    status_parser = subparsers.add_parser("status", help="показать статус проекта")
    status_parser.add_argument("work_dir", type=Path, help="папка проекта")
    status_parser.set_defaults(handler=_handle_status)

    artifacts_parser = subparsers.add_parser("artifacts", help="показать артефакты проекта")
    artifacts_parser.add_argument("work_dir", type=Path, help="папка проекта")
    artifacts_parser.set_defaults(handler=_handle_artifacts)

    config_parser = subparsers.add_parser("config", help="показать настройки проекта")
    config_parser.add_argument("work_dir", type=Path, help="папка проекта")
    config_parser.set_defaults(handler=_handle_config)

    export_srt_parser = subparsers.add_parser("export-srt", help="экспортировать субтитры в формате SRT")
    export_srt_parser.add_argument("work_dir", type=Path, help="папка проекта")
    export_srt_parser.set_defaults(handler=_handle_export_srt)

    export_vtt_parser = subparsers.add_parser("export-vtt", help="экспортировать субтитры в формате WebVTT")
    export_vtt_parser.add_argument("work_dir", type=Path, help="папка проекта")
    export_vtt_parser.set_defaults(handler=_handle_export_vtt)

    timing_parser = subparsers.add_parser("timing-report", help="отчёт по таймингам сегментов")
    timing_parser.add_argument("work_dir", type=Path, help="папка проекта")
    timing_parser.set_defaults(handler=_handle_timing_report)

    review_parser = subparsers.add_parser("review", help="отчёт ревью перевода")
    review_parser.add_argument("work_dir", type=Path, help="папка проекта")
    review_parser.set_defaults(handler=_handle_review)

    # batch run — запуск нескольких проектов
    batch_parser = subparsers.add_parser(
        "batch",
        help="запустить пайплайн для нескольких проектов (до 50)"
    )
    batch_parser.add_argument(
        "work_dirs",
        nargs="+",
        type=Path,
        help="папки проектов для пакетного запуска",
    )
    batch_parser.add_argument("--force", action="store_true")
    batch_parser.add_argument("--provider", choices=["fake", "legacy"], default="fake")
    batch_parser.set_defaults(handler=_handle_batch)

    # watch — ждать завершения проекта с прогресс-баром
    watch_parser = subparsers.add_parser(
        "watch",
        help="следить за прогрессом запущенного проекта"
    )
    watch_parser.add_argument("work_dir", type=Path, help="папка проекта")
    watch_parser.add_argument(
        "--interval", type=float, default=3.0,
        help="интервал опроса в секундах (default: 3)"
    )
    watch_parser.set_defaults(handler=_handle_watch)

    # download — скачать видео по URL
    dl_parser = subparsers.add_parser(
        "download",
        help="скачать видео по URL (YouTube, Vimeo и др.) через yt-dlp"
    )
    dl_parser.add_argument("url", help="URL видео")
    dl_parser.add_argument(
        "--output-dir", type=Path, default=Path("."),
        help="директория для сохранения (default: текущая)"
    )
    dl_parser.add_argument(
        "--format",
        default="bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        help="yt-dlp формат",
    )
    dl_parser.set_defaults(handler=_handle_download)

    server_parser = subparsers.add_parser("server", help="запустить локальный API сервер")
    server_parser.add_argument("--host", default="127.0.0.1", help="хост для сервера")
    server_parser.add_argument("--port", type=int, default=8002, help="порт для сервера")
    server_parser.add_argument("--work-root", type=Path, default=Path("runs"), help="корень рабочих папок")
    server_parser.set_defaults(handler=_handle_server)

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

    runner = PipelineRunner(_build_stages(args.provider, project.config), force=args.force)
    runs = runner.run(StageContext(project=project, store=store))
    restored = store.load_project(project.work_dir)
    summary = _project_summary(restored)
    summary["runs"] = [run.to_dict() for run in runs]
    return summary


def _handle_preflight(args: argparse.Namespace) -> dict:
    """Проверить входной файл и окружение без запуска пайплайна."""

    return run_preflight(args.input_video, args.provider).to_dict()


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


def _handle_export_srt(args: argparse.Namespace) -> dict:
    """Экспортировать переведенные субтитры в формате SRT."""

    store = ProjectStore(args.work_dir.parent)
    project = store.load_project(args.work_dir)
    output = store.export_subtitles(project, fmt="srt")
    return {"format": "srt", "path": output.as_posix()}


def _handle_export_vtt(args: argparse.Namespace) -> dict:
    """Экспортировать переведенные субтитры в формате WebVTT."""

    store = ProjectStore(args.work_dir.parent)
    project = store.load_project(args.work_dir)
    output = store.export_subtitles(project, fmt="vtt")
    return {"format": "vtt", "path": output.as_posix()}


def _handle_timing_report(args: argparse.Namespace) -> dict:
    """Вернуть JSON-отчёт по таймингам сегментов проекта."""

    from translate_video.export.timing_report import build_timing_report  # noqa: PLC0415

    project = ProjectStore(args.work_dir.parent).load_project(args.work_dir)
    return build_timing_report(project.segments)


def _handle_review(args: argparse.Namespace) -> dict:
    """Вернуть JSON-отчёт ревью перевода для ручной проверки."""

    from translate_video.export.review import build_review_artifact  # noqa: PLC0415

    project = ProjectStore(args.work_dir.parent).load_project(args.work_dir)
    return build_review_artifact(project.segments, project.config.to_dict())


def _handle_server(args: argparse.Namespace) -> dict | None:
    """Запустить FastAPI сервер."""

    import uvicorn
    import os

    os.environ["WORK_ROOT"] = str(args.work_root)
    uvicorn.run("translate_video.api.main:app", host=args.host, port=args.port, reload=True)
    return None


def _handle_batch(args: argparse.Namespace) -> dict:
    """Пакетный запуск нескольких проектов последовательно."""
    MAX_BATCH = 50
    work_dirs = args.work_dirs[:MAX_BATCH]
    results = []
    for wd in work_dirs:
        store = ProjectStore(wd.parent)
        try:
            project = store.load_project(wd)
            runner = PipelineRunner(
                _build_stages(args.provider, project.config),
                force=args.force,
            )
            runs = runner.run(StageContext(project=project, store=store))
            results.append({
                "project_id": project.id,
                "status": project.status.value,
                "stages": len(runs),
            })
        except Exception as exc:  # noqa: BLE001
            results.append({"project_id": str(wd), "error": str(exc)})
    return {"batch_results": results, "total": len(results)}


def _handle_watch(args: argparse.Namespace) -> dict:
    """Следить за статусом проекта до завершения (polling).

    Ctrl+C — выводит последний известный статус и завершается корректно.
    """
    import time
    import sys

    store = ProjectStore(args.work_dir.parent)
    interval = max(1.0, args.interval)
    print(f"Следим за проектом: {args.work_dir.name} (Ctrl+C для выхода)", file=sys.stderr)
    last_project = None
    try:
        while True:
            try:
                project = store.load_project(args.work_dir)
                last_project = project
            except Exception as exc:
                print(f"\rОшибка загрузки: {exc}  ", end="", flush=True, file=sys.stderr)
                time.sleep(interval)
                continue

            status = project.status.value
            pct = getattr(project, "progress_percent", None)
            bar = f" {pct:.0f}%" if pct is not None else ""
            print(f"\r[{status}]{bar}  ", end="", flush=True, file=sys.stderr)

            if status in ("completed", "failed", "cancelled"):
                print("", file=sys.stderr)
                return _project_summary(project)

            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n[watch] Прерван пользователем.", file=sys.stderr)
        if last_project:
            return _project_summary(last_project)
        return {"error": "watch прерван до получения данных"}


def _handle_download(args: argparse.Namespace) -> dict:
    """Скачать видео по URL через yt-dlp."""
    try:
        import yt_dlp  # noqa: PLC0415
    except ImportError as exc:
        raise SystemExit("yt-dlp не установлен. Запустите: pip install yt-dlp") from exc

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    ydl_opts = {
        "format": args.format,
        "outtmpl": str(output_dir / "%(title)s.%(ext)s"),
        "merge_output_format": "mp4",
        "retries": 3,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(args.url, download=True)
        filename = ydl.prepare_filename(info)

    return {
        "title": info.get("title", ""),
        "duration_s": info.get("duration"),
        "filename": filename,
        "url": args.url,
    }


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


def _build_stages(provider: str, config=None):
    """Делегировать сборку этапов в pipeline.utils."""
    return _build_stages_impl(provider, project_config=config)


def _project_summary(project) -> dict:
    """Делегировать формирование сводки в pipeline.utils."""
    return _project_summary_impl(project)


def _values(enum_type) -> list[str]:
    """Вернуть строковые значения enum для argparse choices."""

    return [item.value for item in enum_type]


if __name__ == "__main__":
    raise SystemExit(main())
