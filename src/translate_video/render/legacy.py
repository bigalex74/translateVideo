"""MoviePy-рендерер закадровой озвучки.

Безопасная подгонка TTS:
- по умолчанию не ускоряем и не обрезаем TTS;
- если TTS длиннее слота — ставим QA-флаг и мягко сдвигаем следующие реплики;
- ускорение доступно только через allow_render_audio_speedup=True;
- обрезка доступна только через allow_render_audio_trim=True для явного режима.
"""

from __future__ import annotations

# Дефолты используются для старых project.json без новых полей конфигурации.
_DEFAULT_MAX_SPEED = 1.3
_DEFAULT_GAP = 0.05


class MoviePyVoiceoverRenderer:
    """Собирает итоговое видео из исходного видео и TTS-сегментов."""

    def __init__(
        self,
        video_clip_factory=None,
        audio_clip_factory=None,
        composite_audio_factory=None,
        volume_filter=None,
        speed_effect_factory=None,
    ) -> None:
        self.video_clip_factory = video_clip_factory or _moviepy_video_clip
        self.audio_clip_factory = audio_clip_factory or _moviepy_audio_clip
        self.composite_audio_factory = composite_audio_factory or _moviepy_composite_audio
        self.volume_filter = volume_filter or _moviepy_volume_filter
        self.speed_effect_factory = speed_effect_factory or _moviepy_speedx

    def render(self, project, segments):
        """Наложить TTS-сегменты на приглушенное исходное аудио и записать MP4."""

        output = project.work_dir / "output" / "translated.mp4"
        video = self.video_clip_factory(str(project.input_video))
        clips = []
        final_video = None
        try:
            if video.audio is not None:
                clips.append(self.volume_filter(video.audio, project.config.original_audio_volume))

            previous_speech_end: float | None = None
            for segment in segments:
                if not segment.tts_path:
                    continue

                speech = self.audio_clip_factory(str(project.work_dir / segment.tts_path))

                # Устранение наложений: TTS-клип не должен заходить на следующий сегмент.
                # Приоритет TVIDEO-041 — сохранить смысл, а не молча отрезать хвост фразы.
                slot = segment.end - segment.start
                gap = getattr(project.config, "render_gap", _DEFAULT_GAP)
                max_speed = getattr(project.config, "render_max_speed", _DEFAULT_MAX_SPEED)
                allow_speedup = getattr(project.config, "allow_render_audio_speedup", False)
                allow_trim = getattr(project.config, "allow_render_audio_trim", False)
                allow_shift = getattr(project.config, "allow_timeline_shift", True)
                max_shift = getattr(project.config, "max_timeline_shift", 1.5)
                max_duration = max(0.1, slot - gap)

                if speech.duration > max_duration and not allow_trim:
                    _add_qa_flag(segment, "render_audio_overflow")

                if allow_speedup and speech.duration > max_duration and max_speed > 1.0:
                    # Явный fast-режим: пытаемся ускорить без изменения тона.
                    speed = speech.duration / max_duration
                    if speed <= max_speed:
                        sped = self.speed_effect_factory(speech, speed)
                        if sped is speech:
                            _add_qa_flag(segment, "render_speed_fallback")
                        else:
                            _add_qa_flag(segment, "render_audio_speedup")
                        speech = sped
                    else:
                        # Ускорение не спасает — ускоряем до максимума и фиксируем overflow.
                        sped = self.speed_effect_factory(speech, max_speed)
                        if sped is speech:
                            _add_qa_flag(segment, "render_speed_fallback")
                        else:
                            _add_qa_flag(segment, "render_audio_speedup")
                        speech = sped
                        new_duration = speech.duration
                        if new_duration > max_duration:
                            if allow_trim:
                                speech = speech.subclip(0, max_duration)
                                _add_qa_flag(segment, "render_audio_trimmed")
                            else:
                                _add_qa_flag(segment, "render_audio_overflow")

                    if speech.duration > max_duration and not allow_trim:
                        _add_qa_flag(segment, "render_audio_overflow")
                elif allow_trim and speech.duration > max_duration:
                    speech = speech.subclip(0, max_duration)
                    _add_qa_flag(segment, "render_audio_trimmed")

                start = segment.start
                if allow_shift and previous_speech_end is not None:
                    shifted_start = max(start, previous_speech_end + gap)
                    if shifted_start > start:
                        allowed_start = start + max_shift
                        if shifted_start > allowed_start:
                            shifted_start = allowed_start
                            _add_qa_flag(segment, "timeline_shift_limit_reached")
                        if shifted_start > start:
                            start = shifted_start
                            _add_qa_flag(segment, "timeline_shifted")

                previous_speech_end = start + speech.duration
                video_duration = getattr(video, "duration", None)
                if video_duration is not None and previous_speech_end > video_duration:
                    _add_qa_flag(segment, "timeline_audio_extends_video")

                clips.append(speech.set_start(start))

            if not clips:
                raise ValueError("нет аудиоклипов для рендера")

            final_audio = self.composite_audio_factory(clips)
            final_video = video.set_audio(final_audio)
            final_video.write_videofile(
                str(output),
                codec="libx264",
                audio_codec="aac",
                logger=None,
            )
        finally:
            for clip in clips:
                clip.close()
            if final_video is not None and final_video is not video:
                final_video.close()
            video.close()
        return output


def _add_qa_flag(segment, flag: str) -> None:
    """Добавить QA-флаг сегменту без дублей."""

    if flag not in segment.qa_flags:
        segment.qa_flags.append(flag)


def _moviepy_video_clip(path: str):
    """Лениво импортировать `VideoFileClip`."""

    from moviepy.editor import VideoFileClip

    return VideoFileClip(path)


def _moviepy_audio_clip(path: str):
    """Лениво импортировать `AudioFileClip`."""

    from moviepy.editor import AudioFileClip

    return AudioFileClip(path)


def _moviepy_composite_audio(clips):
    """Лениво импортировать `CompositeAudioClip`."""

    from moviepy.editor import CompositeAudioClip

    return CompositeAudioClip(clips)


def _moviepy_volume_filter(clip, volume: float):
    """Лениво импортировать фильтр громкости MoviePy."""

    from moviepy.audio.fx.all import volumex

    return volumex(clip, volume)


def _moviepy_speedx(clip, factor: float):
    """Ускорить аудиоклип через ffmpeg atempo — pitch-neutral (moviepy 1.x совместимо).

    fl_time изменяет питч голоса (chipmunk effect) — неприемлемо для озвучки.
    ffmpeg atempo — промышленный стандарт pitch-корректного ускорения.

    Ограничение atempo: один фильтр [0.5, 2.0]. Для factor>2.0 цепочка фильтров.
    """
    import subprocess
    import tempfile
    import os
    from pathlib import Path
    from moviepy.editor import AudioFileClip

    # Получаем исходный файл
    if not hasattr(clip, 'filename') or not clip.filename:
        # Нет физического файла — сохраняем во временный
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
            tmp_in = f.name
        clip.write_audiofile(tmp_in, logger=None)
        owns_input = True
    else:
        tmp_in = clip.filename
        owns_input = False

    with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
        tmp_out = f.name

    try:
        # Строим цепочку фильтров atempo (каждый ограничен [0.5, 2.0])
        remaining = factor
        filters = []
        while remaining > 2.0:
            filters.append('atempo=2.0')
            remaining /= 2.0
        while remaining < 0.5:
            filters.append('atempo=0.5')
            remaining /= 0.5
        filters.append(f'atempo={remaining:.6f}')
        filter_str = ','.join(filters)

        subprocess.run(
            ['ffmpeg', '-y', '-i', tmp_in, '-filter:a', filter_str, tmp_out],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        result = AudioFileClip(tmp_out)
        # Сохраняем путь к temp файлу для последующей очистки
        result._tmp_speedx_file = tmp_out
        return result
    except Exception:
        # Fallback: без ускорения лучше тишины
        return clip
    finally:
        if owns_input and os.path.exists(tmp_in):
            os.unlink(tmp_in)
