"""MoviePy-адаптер медиа-операций из устаревшего скрипта."""

from __future__ import annotations


class LegacyMoviePyMediaProvider:
    """Извлекает аудио из видео через MoviePy."""

    def __init__(self, video_clip_factory=None) -> None:
        self.video_clip_factory = video_clip_factory or _moviepy_video_clip

    def extract_audio(self, project):
        """Извлечь исходное аудио в папку проекта."""

        output = project.work_dir / "source_audio.wav"
        video = self.video_clip_factory(str(project.input_video))
        try:
            if video.audio is None:
                raise ValueError("видео не содержит аудиодорожку")
            video.audio.write_audiofile(str(output), logger=None)
        finally:
            video.close()
        return output


def _moviepy_video_clip(path: str):
    """Лениво импортировать MoviePy, чтобы тесты не требовали зависимость."""

    from moviepy.editor import VideoFileClip

    return VideoFileClip(path)
