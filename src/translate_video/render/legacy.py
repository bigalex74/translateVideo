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
                        speech = self.speed_effect_factory(speech, speed)
                    else:
                        # Ускорение не спасает — обрезаем + ускоряем по максимуму
                        speech = self.speed_effect_factory(speech, _MAX_SPEED)
                        new_duration = speech.duration
                        if new_duration > max_duration:
                            speech = speech.subclip(0, max_duration)

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
    """Ускорить аудиоклип через fl_time (moviepy 1.x совместимо).

    audio_speedx не существует в moviepy 1.0.3.
    fl_time(lambda t: t * factor) читает сэмплы быстрее → ускорение.
    """
    return clip.fl_time(lambda t: t * factor, apply_to="audio").set_duration(clip.duration / factor)
