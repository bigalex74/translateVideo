"""Интеграционные тесты этапов пайплайна с имитационными провайдерами."""

import tempfile
import unittest
from pathlib import Path

from translate_video.core.config import PipelineConfig
from translate_video.core.schemas import JobStatus, ProjectStatus, Segment, Stage
from translate_video.core.store import ProjectStore
from translate_video.pipeline import (
    ExtractAudioStage,
    PipelineRunner,
    RenderStage,
    StageContext,
    TimingFitStage,
    TTSStage,
    TranscribeStage,
    TranslateStage,
)


class FakeMediaProvider:
    """Имитационный медиа-провайдер, создающий локальный аудио-артефакт."""

    def extract_audio(self, project):
        """Создать минимальный файл исходного аудио."""

        path = project.work_dir / "source_audio.wav"
        path.write_bytes(b"test audio")
        return path


class FakeTranscriber:
    """Имитационный распознаватель, возвращающий один сегмент."""

    def transcribe(self, audio_path, config):
        """Вернуть заранее известный исходный сегмент."""

        return [Segment(id="seg_1", start=0.0, end=1.0, source_text="Привет")]


class FakeTranslator:
    """Имитационный переводчик, добавляющий код целевого языка к переводу."""

    def translate(self, segments, config):
        """Вернуть переведенные сегменты с сохраненными ID и таймингами."""

        return [
            Segment(
                id=segment.id,
                start=segment.start,
                end=segment.end,
                source_text=segment.source_text,
                translated_text=f"{config.target_language}: Привет",
            )
            for segment in segments
        ]


class FakeTTSProvider:
    """Имитационный TTS-провайдер, создающий файлы озвучки сегментов."""

    def synthesize(self, project, segments):
        """Заполнить `tts_path` и записать минимальные аудиофайлы."""

        for segment in segments:
            tts_path = project.work_dir / "tts" / f"{segment.id}.wav"
            tts_path.write_bytes(b"test speech")
            segment.tts_path = tts_path.relative_to(project.work_dir).as_posix()
        return segments


class FakeTimingFitter:
    """Имитационная подгонка таймингов, сохраняющая перевод без изменений."""

    def fit(self, project, segments, progress_callback=None):
        """Заполнить tts_text перед TTS."""

        total = len(segments)
        if progress_callback is not None:
            progress_callback(0, total, "Подготовка сегментов")
        for segment in segments:
            segment.tts_text = segment.translated_text
        if progress_callback is not None:
            progress_callback(total, total, f"Готово {total}/{total}")
        return segments


class FakeRenderer:
    """Имитационный рендерер, создающий минимальный итоговый видеофайл."""

    def render(self, project, segments):
        """Создать итоговый видео-артефакт."""

        path = project.work_dir / "output" / "translated.mp4"
        path.write_bytes(b"test video")
        return path


class PipelineStagesIntegrationTest(unittest.TestCase):
    """Проверяет совместную работу хранилища, раннера, этапов и имитаций."""

    def test_pipeline_records_artifacts_and_stage_runs(self):
        """Успешный сценарий должен записать артефакты и запуски этапов."""

        with tempfile.TemporaryDirectory() as temp_dir:
            store = ProjectStore(Path(temp_dir) / "runs")
            project = store.create_project(
                "lesson.mp4",
                config=PipelineConfig(source_language="en", target_language="ru"),
                project_id="lesson",
            )
            context = StageContext(project=project, store=store)
            runner = PipelineRunner(
                [
                    ExtractAudioStage(FakeMediaProvider()),
                    TranscribeStage(FakeTranscriber()),
                    TranslateStage(FakeTranslator()),
                    TimingFitStage(FakeTimingFitter()),
                    TTSStage(FakeTTSProvider()),
                    RenderStage(FakeRenderer()),
                ]
            )

            runs = runner.run(context)
            restored = store.load_project(project.work_dir)

            self.assertEqual([run.status for run in runs], [JobStatus.COMPLETED] * 6)
            self.assertEqual([run.stage for run in runs], [
                Stage.EXTRACT_AUDIO,
                Stage.TRANSCRIBE,
                Stage.TRANSLATE,
                Stage.TIMING_FIT,
                Stage.TTS,
                Stage.RENDER,
            ])
            self.assertEqual(restored.artifacts["source_audio"], "source_audio.wav")
            self.assertEqual(restored.artifacts["translated_transcript"], "transcript.translated.json")
            self.assertEqual(restored.artifacts["tts_audio"], "tts")
            self.assertEqual(restored.artifacts["output_video"], "output/translated.mp4")
            self.assertEqual(restored.segments[0].translated_text, "ru: Привет")
            self.assertEqual(restored.segments[0].tts_path, "tts/seg_1.wav")
            self.assertEqual(len(restored.stage_runs), 6)
            self.assertEqual(restored.status, ProjectStatus.COMPLETED)
            self.assertTrue(all(run.started_at for run in restored.stage_runs))
            self.assertTrue(all(run.finished_at for run in restored.stage_runs))
            self.assertEqual(restored.stage_runs[-1].inputs, ["transcript.translated.json", "tts"])

    def test_missing_required_artifact_fails_stage_and_stops_runner(self):
        """Отсутствующий обязательный артефакт должен валить этап и раннер."""

        with tempfile.TemporaryDirectory() as temp_dir:
            store = ProjectStore(Path(temp_dir) / "runs")
            project = store.create_project("lesson.mp4", project_id="lesson")
            context = StageContext(project=project, store=store)
            translate_stage = TranslateStage(FakeTranslator())
            runner = PipelineRunner([TranscribeStage(FakeTranscriber()), translate_stage])

            runs = runner.run(context)
            restored = store.load_project(project.work_dir)

            self.assertEqual(len(runs), 1)
            self.assertEqual(runs[0].status, JobStatus.FAILED)
            self.assertIn("source_audio", runs[0].error)
            self.assertEqual(len(restored.stage_runs), 1)
            self.assertEqual(restored.status, ProjectStatus.FAILED)

    def test_render_requires_tts_audio_artifact(self):
        """Этап рендера должен требовать TTS-артефакт."""

        with tempfile.TemporaryDirectory() as temp_dir:
            store = ProjectStore(Path(temp_dir) / "runs")
            project = store.create_project("lesson.mp4", project_id="lesson")
            context = StageContext(project=project, store=store)
            store.save_segments(
                project,
                [Segment(id="seg_1", start=0.0, end=1.0, source_text="Привет", translated_text="Привет")],
                translated=True,
            )

            run = RenderStage(FakeRenderer()).run(context)

            self.assertEqual(run.status, JobStatus.FAILED)
            self.assertIn("tts_audio", run.error)


if __name__ == "__main__":
    unittest.main()
