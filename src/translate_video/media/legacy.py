"""FFmpeg-адаптер извлечения аудио из видео.

Использует ffmpeg напрямую (без MoviePy), что даёт:
- 16 kHz mono WAV — именно то, что принимает faster-whisper
- 2.5ч видео: ~1.5 GB (MoviePy) → ~170 MB (ffmpeg 16kHz/mono)
- Нет загрузки всего видеопотока в RAM
"""

from __future__ import annotations

import subprocess
from pathlib import Path


class LegacyMoviePyMediaProvider:
    """Извлекает аудио из видео через ffmpeg (16 kHz, mono, WAV).

    Название сохранено для обратной совместимости с utils.py и тестами.
    MoviePy больше не используется — только ffmpeg.
    """

    def extract_audio(self, project) -> Path:
        """Извлечь исходное аудио в 16 kHz mono WAV через ffmpeg."""

        output = project.work_dir / "source_audio.wav"
        cmd = [
            "ffmpeg", "-y",
            "-i", str(project.input_video),
            "-vn",               # без видеодорожки
            "-ar", "16000",      # 16 kHz — нативный формат Whisper
            "-ac", "1",          # mono
            "-sample_fmt", "s16",  # 16-bit PCM
            str(output),
        ]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"ffmpeg завершился с кодом {result.returncode}:\n{result.stderr[-2000:]}"
            )
        return output


def _moviepy_video_clip(path: str):
    """Оставлено для совместимости — в production не используется."""
    from moviepy.editor import VideoFileClip  # noqa: PLC0415
    return VideoFileClip(path)
