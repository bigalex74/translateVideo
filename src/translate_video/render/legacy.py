"""MoviePy-рендерер закадровой озвучки."""

from __future__ import annotations


class MoviePyVoiceoverRenderer:
    """Собирает итоговое видео из исходного видео и TTS-сегментов."""

    def __init__(
        self,
        video_clip_factory=None,
        audio_clip_factory=None,
        composite_audio_factory=None,
        volume_filter=None,
    ) -> None:
        self.video_clip_factory = video_clip_factory or _moviepy_video_clip
        self.audio_clip_factory = audio_clip_factory or _moviepy_audio_clip
        self.composite_audio_factory = composite_audio_factory or _moviepy_composite_audio
        self.volume_filter = volume_filter or _moviepy_volume_filter

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
