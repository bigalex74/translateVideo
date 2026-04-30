"""
Скрипт создания синтетического тестового видео для e2e-тестов.

Создаёт 8-секундное видео (1280x720, 25fps) с тональным аудио-треком,
имитирующим 3 сегмента английской речи. Не требует системного ffmpeg —
использует imageio-ffmpeg с встроенным бинарником.

Использование:
    python3 tests/e2e/fixtures/create_test_video.py

Установка зависимости (один раз):
    pip install imageio[ffmpeg]
"""

from __future__ import annotations

import math
import struct
import sys
import wave
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent
OUTPUT_VIDEO = FIXTURES_DIR / "sample_en.mp4"
OUTPUT_AUDIO = FIXTURES_DIR / "sample_audio.wav"

# Параметры видео
FPS = 25
DURATION_SEC = 8
WIDTH = 1280
HEIGHT = 720

# Текст, который «произносится» в видео (3 сегмента)
SPEECH_SEGMENTS = [
    (0.5, 3.0, "Hello, this is a test video."),
    (3.5, 6.0, "It is used for automated e2e tests."),
    (6.2, 7.8, "Translation pipeline works great."),
]

# Частота тонального сигнала для каждого сегмента (Гц)
TONE_FREQUENCIES = [440, 880, 660]

# Параметры аудио
SAMPLE_RATE = 16000


def _generate_wav(output_path: Path) -> None:
    """Создать синтетический WAV-файл с тональными сигналами на месте речи."""

    total_samples = SAMPLE_RATE * DURATION_SEC
    audio_data = [0.0] * total_samples

    for seg_index, (start, end, _text) in enumerate(SPEECH_SEGMENTS):
        freq = TONE_FREQUENCIES[seg_index % len(TONE_FREQUENCIES)]
        for i in range(int(start * SAMPLE_RATE), min(int(end * SAMPLE_RATE), total_samples)):
            t = (i - int(start * SAMPLE_RATE)) / SAMPLE_RATE
            # Синусоида с плавным нарастанием и затуханием (fade 0.05s)
            fade_in = min(t / 0.05, 1.0)
            fade_out = min((end - start - t) / 0.05, 1.0)
            envelope = min(fade_in, fade_out)
            audio_data[i] = envelope * 0.5 * math.sin(2 * math.pi * freq * t)

    # Конвертировать float [-1, 1] в int16
    samples_int16 = [max(-32767, min(32767, int(v * 32767))) for v in audio_data]

    with wave.open(str(output_path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # int16 = 2 байта
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(struct.pack(f"<{len(samples_int16)}h", *samples_int16))

    print(f"  ✅ WAV создан: {output_path} ({len(samples_int16)} samples, {DURATION_SEC}s)")


def _get_ffmpeg_exe() -> str:
    """Найти ffmpeg через imageio-ffmpeg или в системном PATH."""

    try:
        import imageio_ffmpeg  # noqa: PLC0415

        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        pass
    import shutil  # noqa: PLC0415

    path = shutil.which("ffmpeg")
    if path:
        return path
    raise RuntimeError(
        "ffmpeg не найден. Установите imageio[ffmpeg]: pip install imageio[ffmpeg]"
    )


def create_test_video(output: Path = OUTPUT_VIDEO) -> Path:
    """
    Создать синтетическое тестовое видео с тональным аудио-треком.

    Видео содержит:
    - Тёмно-синий фон 1280×720, 25fps, 8 секунд
    - Моно WAV 16 кГц с тональными сигналами на месте 3 речевых сегментов

    Возвращает путь к созданному файлу.
    """

    import subprocess  # noqa: PLC0415

    output.parent.mkdir(parents=True, exist_ok=True)

    # 1. Создаём синтетический WAV
    print("Шаг 1: Генерация аудио...")
    _generate_wav(OUTPUT_AUDIO)

    # 2. Рендеримм MP4 через ffmpeg
    print("Шаг 2: Рендер видео...")
    ffmpeg = _get_ffmpeg_exe()

    cmd = [
        ffmpeg,
        "-y",  # перезаписать без подтверждения
        # Видеовход: синтетический цветной фон через lavfi
        "-f", "lavfi",
        "-i", f"color=c=0x1a1a2e:size={WIDTH}x{HEIGHT}:rate={FPS}:duration={DURATION_SEC}",
        # Аудиовход: сгенерированный WAV
        "-i", str(OUTPUT_AUDIO),
        # Кодеки — без текстовых наложений (не нужны шрифты)
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "28",
        "-c:a", "aac",
        "-b:a", "64k",
        "-t", str(DURATION_SEC),
        str(output),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("STDERR ffmpeg:", result.stderr[-2000:])
        raise RuntimeError(f"ffmpeg завершился с кодом {result.returncode}")

    size_kb = output.stat().st_size // 1024
    print(f"  ✅ Видео создано: {output} ({size_kb} КБ, {DURATION_SEC}с)")
    return output


def print_segment_info() -> None:
    """Вывести информацию о сегментах для справки при написании тестов."""

    print("\n📋 Ожидаемые сегменты транскрипции:")
    for i, (start, end, text) in enumerate(SPEECH_SEGMENTS, 1):
        print(f"  [{i}] {start:.1f}s – {end:.1f}s: \"{text}\"")
    print(
        "\n💡 Используйте в e2e-тестах:\n"
        "   from tests.e2e.fixtures.create_test_video import OUTPUT_VIDEO, SPEECH_SEGMENTS\n"
        "   assert OUTPUT_VIDEO.exists()"
    )


if __name__ == "__main__":
    print("🎬 Создание тестового видео для e2e...")
    try:
        path = create_test_video()
        print_segment_info()
        print(f"\n✅ Готово: {path}")
        sys.exit(0)
    except Exception as exc:
        print(f"\n❌ Ошибка: {exc}", file=sys.stderr)
        sys.exit(1)
