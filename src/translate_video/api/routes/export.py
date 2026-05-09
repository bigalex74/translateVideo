"""ADR-001 Фаза 1: Export Router — выделение export endpoints из projects.py.

Этот модуль содержит все export-related endpoints для проектов.
URL prefix идентичен projects.py (backward compat).

## Endpoints
- GET /{project_id}/export/zip — ZIP всех артефактов (NC11-01)
- GET /{project_id}/export/subtitles-all — ZIP всех форматов субтитров (Z1.12)
- GET /{project_id}/export/script — Скрипт перевода (TXT/DOCX/TSV) (Z1.11)
- GET /{project_id}/export-audio — MP3/WAV аудиодорожка дубляжа (I7)

## Стратегия декомпозиции (ADR-001)
- Endpoints реализованы ЗДЕСЬ (не в projects.py)
- projects.py содержит stub-redirects для backward compat (deprecated)
- После R15 stub-redirects удаляются
"""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi import Path as FastAPIPath
from fastapi.responses import Response, StreamingResponse

from translate_video.api.routes.projects import get_store  # ADR-001: get_store из projects до создания deps.py
from translate_video.core.store import ProjectStore, sanitize_project_id

export_router = APIRouter(tags=["Export"])


# ─── GET /{project_id}/export/zip ─────────────────────────────────────────────

@export_router.get(
    "/{project_id}/export/zip",
    summary="Экспортировать весь проект как ZIP (NC11-01 / ADR-001)",
)
def export_project_zip_v2(
    project_id: str = FastAPIPath(...),
    store: ProjectStore = Depends(get_store),
):
    """Экспортирует все текстовые артефакты проекта в ZIP-архив.

    Включает: все форматы субтитров (SRT, VTT, ASS, SBV), скрипт перевода
    (TXT, TSV), project.json. Видеофайлы НЕ включаются.

    **ADR-001 Фаза 1:** Перенесён из projects.py → export.py.
    """
    safe_id = sanitize_project_id(project_id)
    try:
        project = store.load_project(store.root / safe_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        # project.json
        zf.writestr(
            "project.json",
            json.dumps(project.to_dict(), ensure_ascii=False, indent=2, default=str),
        )

        if project.segments:
            for fmt in ("srt", "vtt", "ass", "sbv"):
                try:
                    data = store.export_subtitles(project, fmt)
                    zf.writestr(f"{safe_id}.{fmt}", data)
                except Exception:
                    pass

            # Скрипт перевода (TXT)
            script_lines = [
                f"[{s.start:.1f}-{s.end:.1f}] {s.translated_text or ''}"
                for s in project.segments
            ]
            zf.writestr(f"{safe_id}_script.txt", "\n".join(script_lines))

            # TSV
            tsv_lines = ["start\tend\tsource\ttranslation"] + [
                f"{s.start}\t{s.end}\t{s.source_text or ''}\t{s.translated_text or ''}"
                for s in project.segments
            ]
            zf.writestr(f"{safe_id}_script.tsv", "\n".join(tsv_lines))

    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename={safe_id}.zip",
            "X-Export-Router": "v2",  # индикатор нового router
        },
    )


# ─── GET /{project_id}/export/subtitles-all ───────────────────────────────────

@export_router.get(
    "/{project_id}/export/subtitles-all",
    summary="Скачать все форматы субтитров в ZIP (Z1.12 / ADR-001)",
)
def export_all_subtitles_v2(
    project_id: str = FastAPIPath(...),
    store: ProjectStore = Depends(get_store),
):
    """Скачать SRT + VTT + ASS + SBV в одном ZIP-архиве.

    Форматы: YouTube (SRT/SBV), Vimeo (VTT), Aegisub (ASS).
    **ADR-001 Фаза 1:** Перенесён из projects.py → export.py.
    """
    safe_id = sanitize_project_id(project_id)
    try:
        project = store.load_project(store.root / safe_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")
    if not project.segments:
        raise HTTPException(
            status_code=404,
            detail="Субтитры ещё не созданы — запустите перевод",
        )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for fmt in ("srt", "vtt", "ass", "sbv"):
            try:
                data = store.export_subtitles(project, fmt)
                zf.writestr(f"{safe_id}.{fmt}", data)
            except Exception:
                pass

    return Response(
        content=buf.getvalue(),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_id}_subtitles.zip"',
            "X-Export-Router": "v2",
        },
    )


# ─── GET /{project_id}/export/script ──────────────────────────────────────────

@export_router.get(
    "/{project_id}/export/script",
    summary="Скачать скрипт перевода (TXT/DOCX/TSV) (Z1.11 / ADR-001)",
)
def export_script_v2(
    project_id: str = FastAPIPath(...),
    format: str = "txt",  # noqa: A002
    include_timecodes: bool = True,
    include_source: bool = False,
    store: ProjectStore = Depends(get_store),
):
    """Экспортировать скрипт перевода всех сегментов.

    format: txt (default) | tsv | docx
    include_timecodes: включить таймкоды [MM:SS.ms]
    include_source: включить оригинальный текст под каждым переводом

    **ADR-001 Фаза 1:** Перенесён из projects.py → export.py.
    """
    from io import StringIO  # noqa: PLC0415

    safe_id = sanitize_project_id(project_id)
    try:
        project = store.load_project(store.root / safe_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")
    if not project.segments:
        raise HTTPException(
            status_code=404,
            detail="Сегменты не найдены — запустите транскрипцию",
        )

    if format == "tsv":
        buf = StringIO()
        buf.write("start\tend\tsource\ttranslated\n")
        for seg in project.segments:
            start = f"{seg.start:.2f}"
            end = f"{seg.end:.2f}"
            src = (seg.source_text or "").replace("\t", " ")
            tgt = (seg.translated_text or "").replace("\t", " ")
            buf.write(f"{start}\t{end}\t{src}\t{tgt}\n")
        return Response(
            content=buf.getvalue().encode("utf-8"),
            media_type="text/tab-separated-values",
            headers={"Content-Disposition": f'attachment; filename="{safe_id}_script.tsv"'},
        )

    if format == "docx":
        # Генерация минимального DOCX (Office Open XML)
        from io import BytesIO  # noqa: PLC0415
        content_types_xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml"'
            ' ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            "</Types>"
        )
        rels_xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1"'
            ' Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"'
            ' Target="word/document.xml"/>'
            "</Relationships>"
        )
        paras = []
        for i, seg in enumerate(project.segments, 1):
            if include_timecodes:
                start_ts = f"{int(seg.start // 60):02d}:{seg.start % 60:05.2f}"
                end_ts = f"{int(seg.end // 60):02d}:{seg.end % 60:05.2f}"
                paras.append(
                    f"<w:p><w:r><w:rPr><w:b/></w:rPr>"
                    f"<w:t>[{i}] {start_ts} → {end_ts}</w:t></w:r></w:p>"
                )
            if include_source:
                paras.append(
                    f"<w:p><w:r><w:rPr><w:color w:val=\"666666\"/></w:rPr>"
                    f"<w:t>ОР: {seg.source_text or ''}</w:t></w:r></w:p>"
                )
            paras.append(
                f"<w:p><w:r><w:t xml:space=\"preserve\">"
                f"ПЕР: {seg.translated_text or '(нет перевода)'}</w:t></w:r></w:p>"
            )
            paras.append("<w:p/>")
        doc_xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            "<w:body>"
            + "".join(paras)
            + "</w:body></w:document>"
        )
        b = BytesIO()
        with zipfile.ZipFile(b, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("[Content_Types].xml", content_types_xml)
            zf.writestr("_rels/.rels", rels_xml)
            zf.writestr("word/document.xml", doc_xml)
        return Response(
            content=b.getvalue(),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f'attachment; filename="{safe_id}_script.docx"'},
        )

    # TXT (default)
    buf = StringIO()
    buf.write(f"ПЕРЕВОД: {safe_id}\n")
    buf.write("=" * 60 + "\n\n")
    for i, seg in enumerate(project.segments, 1):
        if include_timecodes:
            start_ts = f"{int(seg.start // 60):02d}:{seg.start % 60:05.2f}"
            end_ts = f"{int(seg.end // 60):02d}:{seg.end % 60:05.2f}"
            buf.write(f"[{i}] {start_ts} → {end_ts}\n")
        if include_source:
            buf.write(f"  ОР: {seg.source_text or ''}\n")
        buf.write(f"  ПЕР: {seg.translated_text or '(нет перевода)'}\n\n")
    return Response(
        content=buf.getvalue().encode("utf-8"),
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{safe_id}_script.txt"'},
    )


# ─── GET /{project_id}/export-audio ───────────────────────────────────────────

@export_router.get(
    "/{project_id}/export-audio",
    summary="Скачать аудиодорожку дубляжа MP3/WAV (I7 / ADR-001)",
)
def export_audio_v2(
    project_id: str = FastAPIPath(...),
    format: str = "mp3",  # noqa: A002
    store: ProjectStore = Depends(get_store),
):
    """Экспортировать аудиодорожку дубляжа (TTS без видео).

    format: mp3 (default) | wav

    Используется когда нужна только озвучка без видео.
    **ADR-001 Фаза 1:** Перенесён из projects.py → export.py.
    """
    import subprocess  # noqa: PLC0415

    safe_id = sanitize_project_id(project_id)
    try:
        project = store.load_project(store.root / safe_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")

    # Ищем TTS audio папку
    tts_dir = project.work_dir / "tts"
    if not tts_dir.exists():
        raise HTTPException(
            status_code=404,
            detail="TTS аудио не найдено — запустите этап озвучки (TTS)",
        )

    # Берём все .wav/.mp3 файлы из tts/ отсортированные по имени (порядок сегментов)
    audio_files = sorted(
        [f for f in tts_dir.iterdir() if f.suffix in (".wav", ".mp3")],
        key=lambda p: p.name,
    )
    if not audio_files:
        raise HTTPException(
            status_code=404,
            detail="TTS файлы не найдены в директории озвучки",
        )

    # Конкатенируем через ffmpeg
    concat_list = project.work_dir / "tts" / "_concat.txt"
    try:
        concat_list.write_text(
            "\n".join(f"file '{f.resolve()}'" for f in audio_files),
            encoding="utf-8",
        )
        out_path = project.work_dir / f"dubbing.{format}"
        result = subprocess.run(
            [
                "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                "-i", str(concat_list),
                "-acodec", "libmp3lame" if format == "mp3" else "pcm_s16le",
                str(out_path),
            ],
            capture_output=True,
            timeout=120,
        )
        if result.returncode != 0:
            raise HTTPException(
                status_code=500,
                detail=f"ffmpeg ошибка конкатенации: {result.stderr.decode()[:200]}",
            )
        content = out_path.read_bytes()
        out_path.unlink(missing_ok=True)
    finally:
        concat_list.unlink(missing_ok=True)

    mime = "audio/mpeg" if format == "mp3" else "audio/wav"
    return Response(
        content=content,
        media_type=mime,
        headers={"Content-Disposition": f'attachment; filename="{safe_id}_dubbing.{format}"'},
    )
