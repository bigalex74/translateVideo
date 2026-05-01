"""MoviePy-рендерер закадровой озвучки.

Устранение наложений TTS:
- Если TTS-клип длиннее временного слота — ускоряем до 1.3x.
- Если всё ещё длиннее — обрезаем с 50мс зазором.
"""

from __future__ import annotations

# Максимальный коэффициент ускорения TTS перед обрезкой
_MAX_SPEED = 1.3
# Минимальный зазор между сегментами (секунды)
_GAP = 0.05


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

            for segment in segments:
                if not segment.tts_path:
                    continue

                speech = self.audio_clip_factory(str(project.work_dir / segment.tts_path))

                # Устранение наложений: TTS-клип не должен заходить на следующий сегмент
                slot = segment.end - segment.start
                max_duration = max(0.1, slot - _GAP)

                if speech.duration > max_duration:
                    # Пытаемся ускорить (до MAX_SPEED)
                    speed = speech.duration / max_duration
                    if speed <= _MAX_SPEED:
                        sped = self.speed_effect_factory(speech, speed)
                        if sped is speech:
                            _add_qa_flag(segment, "render_speed_fallback")
                        else:
                            _add_qa_flag(segment, "render_audio_speedup")
                        speech = sped
                    else:
                        # Ускорение не спасает — обрезаем + ускоряем по максимуму
                        sped = self.speed_effect_factory(speech, _MAX_SPEED)
                        if sped is speech:
                            _add_qa_flag(segment, "render_speed_fallback")
                        else:
                            _add_qa_flag(segment, "render_audio_speedup")
                        speech = sped
                        new_duration = speech.duration
                        if new_duration > max_duration:
                            speech = speech.subclip(0, max_duration)
                            _add_qa_flag(segment, "render_audio_trimmed")

                clips.append(speech.set_start(segment.start))

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
