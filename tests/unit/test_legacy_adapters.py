"""Модульные тесты адаптеров устаревшего пайплайна."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from translate_video.cli import _build_stages
from translate_video.core.config import PipelineConfig
from translate_video.core.schemas import Segment, VideoProject
from translate_video.media.legacy import LegacyMoviePyMediaProvider
from translate_video.render.legacy import MoviePyVoiceoverRenderer
from translate_video.speech.legacy import FasterWhisperTranscriber
from translate_video.translation.legacy import GoogleSegmentTranslator
from translate_video.tts.legacy import EdgeTTSProvider


class LegacyAdaptersTest(unittest.TestCase):
    """Проверяет адаптеры без запуска тяжелых внешних зависимостей."""

    def test_media_provider_extracts_audio_and_closes_video(self):
        """MoviePy-медиа адаптер должен записать аудио и закрыть видео."""

        with tempfile.TemporaryDirectory() as temp_dir:
            project = _project(temp_dir)
            audio = _FakeAudio()
            video = _FakeVideo(audio=audio)
            provider = LegacyMoviePyMediaProvider(video_clip_factory=lambda _path: video)

            output = provider.extract_audio(project)

            self.assertEqual(output, project.work_dir / "source_audio.wav")
            self.assertEqual(audio.written_to, str(output))
            self.assertTrue(video.closed)

    def test_whisper_transcriber_converts_segments(self):
        """Whisper-адаптер должен преобразовать сегменты в схему ядра."""

        model = _FakeWhisperModel([
            SimpleNamespace(start=0.0, end=1.5, text=" Привет ", avg_logprob=-0.1),
            SimpleNamespace(start=1.5, end=2.0, text="  ", avg_logprob=-0.2),
        ])
        transcriber = FasterWhisperTranscriber(model_factory=lambda *args, **kwargs: model)

        segments = transcriber.transcribe(Path("audio.wav"), PipelineConfig())

        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0].source_text, "Привет")
        self.assertEqual(segments[0].start, 0.0)
        self.assertEqual(segments[0].end, 1.5)

    def test_google_translator_preserves_segment_metadata(self):
        """Переводчик должен сохранить ID, тайминги и исходный текст."""

        translator = _FakeTranslator()
        adapter = GoogleSegmentTranslator(translator_factory=lambda **_kwargs: translator)
        source = [Segment(id="seg_1", start=0.0, end=1.0, source_text="Hello")]

        translated = adapter.translate(source, PipelineConfig(source_language="en", target_language="ru"))

        self.assertEqual(translator.calls, ["Hello"])
        self.assertEqual(translated[0].id, "seg_1")
        self.assertEqual(translated[0].translated_text, "ru: Hello")

    def test_edge_tts_provider_writes_paths_and_voice(self):
        """TTS-адаптер должен заполнить путь и выбранный голос."""

        with tempfile.TemporaryDirectory() as temp_dir:
            project = _project(temp_dir, PipelineConfig(target_language="ru"))
            segment = Segment(
                id="seg_1",
                start=0.0,
                end=1.0,
                source_text="Hello",
                translated_text="Привет",
            )
            provider = EdgeTTSProvider(
                communicate_factory=lambda text, voice, rate: _FakeCommunicate(text, voice, rate),
                async_runner=_run_coroutine,
            )

            result = provider.synthesize(project, [segment])

            self.assertEqual(result[0].tts_path, "tts/seg_1.mp3")
            self.assertEqual(result[0].voice, "ru-RU-SvetlanaNeural")
            self.assertTrue((project.work_dir / "tts" / "seg_1.mp3").exists())

    def test_renderer_combines_tts_and_writes_video(self):
        """Рендерер должен собрать аудиоклипы и записать итоговый файл."""

        with tempfile.TemporaryDirectory() as temp_dir:
            project = _project(temp_dir)
            tts_path = project.work_dir / "tts" / "seg_1.mp3"
            tts_path.write_bytes(b"speech")
            segment = Segment(
                id="seg_1",
                start=2.0,
                end=3.0,
                source_text="Hello",
                translated_text="Привет",
                tts_path="tts/seg_1.mp3",
            )
            video = _FakeVideo(audio=_FakeAudio())
            renderer = MoviePyVoiceoverRenderer(
                video_clip_factory=lambda _path: video,
                audio_clip_factory=lambda path: _FakeAudio(path=path),
                composite_audio_factory=lambda clips: _FakeCompositeAudio(clips),
                volume_filter=lambda clip, volume: _FakeAudio(path=f"ducked:{volume}"),
                speed_effect_factory=lambda clip, factor: clip,  # identity — нет реального ffmpeg
            )

            output = renderer.render(project, [segment])

            self.assertEqual(output, project.work_dir / "output" / "translated.mp4")
            self.assertEqual(video.written_to, str(output))
            self.assertTrue(video.closed)

    def test_renderer_marks_speed_fallback(self):
        """Если ускорение вернуло исходный клип, сегмент получает QA-флаг."""

        with tempfile.TemporaryDirectory() as temp_dir:
            project = _project(
                temp_dir,
                PipelineConfig(allow_render_audio_speedup=True, render_max_speed=1.3),
            )
            tts_path = project.work_dir / "tts" / "seg_1.mp3"
            tts_path.write_bytes(b"speech")
            segment = Segment(
                id="seg_1",
                start=0.0,
                end=1.0,
                source_text="Hello",
                translated_text="Привет",
                tts_path="tts/seg_1.mp3",
            )
            video = _FakeVideo(audio=None)
            renderer = MoviePyVoiceoverRenderer(
                video_clip_factory=lambda _path: video,
                audio_clip_factory=lambda path: _FakeAudio(path=path, duration=1.1),
                composite_audio_factory=lambda clips: _FakeCompositeAudio(clips),
                volume_filter=lambda clip, volume: clip,
                speed_effect_factory=lambda clip, factor: clip,
            )

            renderer.render(project, [segment])

            self.assertIn("render_speed_fallback", segment.qa_flags)

    def test_renderer_preserves_overlong_audio_by_default(self):
        """По умолчанию рендер не обрезает длинную озвучку и ставит overflow-флаг."""

        with tempfile.TemporaryDirectory() as temp_dir:
            project = _project(temp_dir, PipelineConfig(allow_render_audio_trim=False))
            tts_path = project.work_dir / "tts" / "seg_1.mp3"
            tts_path.write_bytes(b"speech")
            segment = Segment(
                id="seg_1",
                start=0.0,
                end=1.0,
                source_text="Hello",
                translated_text="Очень длинный перевод, который не помещается в слот.",
                tts_path="tts/seg_1.mp3",
            )
            video = _FakeVideo(audio=None)
            renderer = MoviePyVoiceoverRenderer(
                video_clip_factory=lambda _path: video,
                audio_clip_factory=lambda path: _FakeAudio(path=path, duration=3.0),
                composite_audio_factory=lambda clips: _FakeCompositeAudio(clips),
                volume_filter=lambda clip, volume: clip,
                speed_effect_factory=lambda clip, factor: _FakeAudio(path=clip.path, duration=2.3),
            )

            renderer.render(project, [segment])

            self.assertIn("render_audio_overflow", segment.qa_flags)
            self.assertNotIn("render_audio_trimmed", segment.qa_flags)

    def test_renderer_trims_only_when_explicitly_allowed(self):
        """Обрезка доступна только в явном destructive-режиме конфигурации."""

        with tempfile.TemporaryDirectory() as temp_dir:
            project = _project(
                temp_dir,
                PipelineConfig(
                    allow_render_audio_speedup=True,
                    allow_render_audio_trim=True,
                    render_max_speed=1.3,
                ),
            )
            tts_path = project.work_dir / "tts" / "seg_1.mp3"
            tts_path.write_bytes(b"speech")
            segment = Segment(
                id="seg_1",
                start=0.0,
                end=1.0,
                source_text="Hello",
                translated_text="Очень длинный перевод, который не помещается в слот.",
                tts_path="tts/seg_1.mp3",
            )
            video = _FakeVideo(audio=None)
            renderer = MoviePyVoiceoverRenderer(
                video_clip_factory=lambda _path: video,
                audio_clip_factory=lambda path: _FakeAudio(path=path, duration=3.0),
                composite_audio_factory=lambda clips: _FakeCompositeAudio(clips),
                volume_filter=lambda clip, volume: clip,
                speed_effect_factory=lambda clip, factor: _FakeAudio(path=clip.path, duration=2.3),
            )

            renderer.render(project, [segment])

            self.assertIn("render_audio_trimmed", segment.qa_flags)
            self.assertNotIn("render_audio_overflow", segment.qa_flags)

    def test_renderer_can_trim_without_speedup_when_explicitly_allowed(self):
        """Destructive-режим может обрезать без предварительного ускорения."""

        with tempfile.TemporaryDirectory() as temp_dir:
            project = _project(temp_dir, PipelineConfig(allow_render_audio_trim=True))
            tts_path = project.work_dir / "tts" / "seg_1.mp3"
            tts_path.write_bytes(b"speech")
            segment = Segment(
                id="seg_1",
                start=0.0,
                end=1.0,
                source_text="Hello",
                translated_text="Очень длинный перевод.",
                tts_path="tts/seg_1.mp3",
            )
            video = _FakeVideo(audio=None)
            renderer = MoviePyVoiceoverRenderer(
                video_clip_factory=lambda _path: video,
                audio_clip_factory=lambda path: _FakeAudio(path=path, duration=3.0),
                composite_audio_factory=lambda clips: _FakeCompositeAudio(clips),
                volume_filter=lambda clip, volume: clip,
                speed_effect_factory=lambda clip, factor: clip,
            )

            renderer.render(project, [segment])

            self.assertIn("render_audio_trimmed", segment.qa_flags)
            self.assertNotIn("render_audio_speedup", segment.qa_flags)

    def test_renderer_shifts_following_segment_without_speedup(self):
        """Длинная первая фраза мягко сдвигает следующую без ускорения."""

        with tempfile.TemporaryDirectory() as temp_dir:
            project = _project(
                temp_dir,
                PipelineConfig(allow_timeline_shift=True, max_timeline_shift=1.5),
            )
            first_path = project.work_dir / "tts" / "seg_1.mp3"
            second_path = project.work_dir / "tts" / "seg_2.mp3"
            first_path.write_bytes(b"speech-1")
            second_path.write_bytes(b"speech-2")
            first = Segment(
                id="seg_1",
                start=0.0,
                end=1.0,
                source_text="Hello",
                translated_text="Длинная первая фраза.",
                tts_path="tts/seg_1.mp3",
            )
            second = Segment(
                id="seg_2",
                start=1.0,
                end=2.0,
                source_text="World",
                translated_text="Вторая фраза.",
                tts_path="tts/seg_2.mp3",
            )
            created: list[_FakeAudio] = []

            def audio_factory(path):
                duration = 1.4 if path.endswith("seg_1.mp3") else 0.4
                clip = _FakeAudio(path=path, duration=duration)
                created.append(clip)
                return clip

            video = _FakeVideo(audio=None)
            renderer = MoviePyVoiceoverRenderer(
                video_clip_factory=lambda _path: video,
                audio_clip_factory=audio_factory,
                composite_audio_factory=lambda clips: _FakeCompositeAudio(clips),
                volume_filter=lambda clip, volume: clip,
                speed_effect_factory=lambda clip, factor: clip,
            )

            renderer.render(project, [first, second])

            self.assertEqual(created[0].started_at, 0.0)
            self.assertAlmostEqual(created[1].started_at, 1.45)
            self.assertIn("timeline_shifted", second.qa_flags)

    def test_cli_builds_legacy_stage_chain(self):
        """CLI должен уметь собрать цепочку провайдеров устаревшего скрипта."""

        stages = _build_stages("legacy")

        self.assertEqual(len(stages), 8)  # +RegroupStage + TimingFitStage + ExportSubtitlesStage


def _project(temp_dir: str, config: PipelineConfig | None = None) -> VideoProject:
    """Создать минимальный проект для тестов адаптеров."""

    work_dir = Path(temp_dir) / "lesson"
    (work_dir / "tts").mkdir(parents=True)
    (work_dir / "output").mkdir()
    return VideoProject(
        id="lesson",
        input_video=Path("lesson.mp4"),
        work_dir=work_dir,
        config=config or PipelineConfig(),
    )


def _run_coroutine(coroutine):
    """Выполнить корутину без привязки теста к asyncio.run."""

    try:
        coroutine.send(None)
    except StopIteration:
        return None
    raise AssertionError("тестовая coroutine должна завершиться сразу")


class _FakeAudio:
    """Минимальный аудио-клип для тестов MoviePy-адаптеров."""

    def __init__(self, path: str | None = None, duration: float = 0.5) -> None:
        self.path = path
        self.duration = duration          # нужно для overlap-check в рендерере
        self.written_to: str | None = None
        self.started_at: float | None = None
        self.closed = False

    def write_audiofile(self, path: str, logger=None) -> None:
        self.written_to = path
        Path(path).write_bytes(b"audio")

    def set_start(self, start: float):
        self.started_at = start
        return self

    def subclip(self, start, end):
        clipped = _FakeAudio(path=self.path, duration=end - start)
        return clipped

    def close(self) -> None:
        self.closed = True


class _FakeVideo:
    """Минимальный видео-клип для тестов MoviePy-адаптеров."""

    def __init__(self, audio: _FakeAudio | None = None) -> None:
        self.audio = audio
        self.closed = False
        self.written_to: str | None = None

    def set_audio(self, audio):
        self.audio = audio
        return self

    def write_videofile(self, path: str, codec: str, audio_codec: str, logger=None) -> None:
        self.written_to = path
        Path(path).write_bytes(f"{codec}:{audio_codec}".encode())

    def close(self) -> None:
        self.closed = True


class _FakeWhisperModel:
    """Минимальная модель распознавания для проверки адаптера."""

    def __init__(self, segments) -> None:
        self.segments = segments

    def transcribe(self, audio_path: str, beam_size: int):
        return self.segments, SimpleNamespace(language="en")


class _FakeTranslator:
    """Минимальный переводчик для проверки адаптера."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def translate(self, text: str) -> str:
        self.calls.append(text)
        return f"ru: {text}"


class _FakeCommunicate:
    """Минимальный объект edge-tts для проверки записи файла."""

    def __init__(self, text: str, voice: str, rate: str) -> None:
        self.text = text
        self.voice = voice
        self.rate = rate

    async def save(self, path: str) -> None:
        Path(path).write_text(f"{self.voice}:{self.rate}:{self.text}", encoding="utf-8")


class _FakeCompositeAudio:
    """Минимальный CompositeAudioClip для проверки состава клипов."""

    def __init__(self, clips) -> None:
        self.clips = clips

    def close(self) -> None:
        pass


if __name__ == "__main__":
    unittest.main()
