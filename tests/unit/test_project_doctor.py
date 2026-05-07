"""Project Doctor and safe partial rerun tests."""

import tempfile
from pathlib import Path
from unittest import TestCase

from translate_video.core.schemas import ArtifactKind, JobStatus, Segment, Stage, StageRun
from translate_video.core.store import ProjectStore
from translate_video.pipeline.doctor import diagnose_project, recommend_safe_from_stage


class _Stage:
    def __init__(self, stage: Stage) -> None:
        self.stage = stage


def _stages(*stages: Stage):
    return [_Stage(stage) for stage in stages]


class ProjectDoctorTest(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = ProjectStore(Path(self.temp_dir.name) / "runs")
        self.project = self.store.create_project("video.mp4", project_id="doctor")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_transcribe_without_source_audio_backtracks_to_extract_audio(self):
        plan = recommend_safe_from_stage(
            self.project,
            _stages(Stage.EXTRACT_AUDIO, Stage.TRANSCRIBE),
            "transcribe",
        )

        self.assertTrue(plan.changed)
        self.assertEqual(plan.safe_from_stage, "extract_audio")

    def test_render_without_tts_audio_backtracks_to_tts(self):
        transcript = self.project.work_dir / "transcript.translated.json"
        transcript.write_text("[]", encoding="utf-8")
        self.store.add_artifact(
            self.project,
            ArtifactKind.TRANSLATED_TRANSCRIPT,
            transcript,
            Stage.TRANSLATE,
            "application/json",
        )

        plan = recommend_safe_from_stage(
            self.project,
            _stages(Stage.TRANSLATE, Stage.TTS, Stage.RENDER),
            "render",
        )

        self.assertTrue(plan.changed)
        self.assertEqual(plan.safe_from_stage, "tts")

    def test_diagnose_reports_missing_artifact_file(self):
        missing = self.project.work_dir / "missing.json"
        self.store.add_artifact(
            self.project,
            ArtifactKind.QA_REPORT,
            missing,
            Stage.QA,
            "application/json",
        )

        report = diagnose_project(self.project)

        self.assertFalse(report["ok"])
        self.assertTrue(
            any(issue["code"] == "missing_artifact_file" for issue in report["issues"])
        )

    def test_diagnose_recommends_failed_stage(self):
        self.project.stage_runs = [
            StageRun(stage=Stage.EXTRACT_AUDIO, status=JobStatus.COMPLETED),
            StageRun(stage=Stage.TRANSCRIBE, status=JobStatus.FAILED, error="boom"),
        ]

        report = diagnose_project(self.project, _stages(Stage.EXTRACT_AUDIO, Stage.TRANSCRIBE))

        self.assertEqual(report["requested_from_stage"], "transcribe")
        self.assertEqual(report["recommended_from_stage"], "extract_audio")

    def test_diagnose_reports_segment_summary_and_actions(self):
        self.project.segments = [
            Segment(start=0, end=1, source_text="Hello", translated_text=""),
            Segment(start=1, end=2, source_text="World", translated_text="Мир"),
            Segment(
                start=2,
                end=3,
                source_text="Again",
                translated_text="Снова",
                tts_path="tts/seg_3.mp3",
                qa_flags=["timing_fit_failed"],
                reviewed=False,
            ),
            Segment(
                start=3,
                end=4,
                source_text="Ok",
                translated_text="Ок",
                qa_flags=["length_warning"],
                reviewed=True,
            ),
        ]

        report = diagnose_project(self.project)
        summary = report["segment_summary"]
        actions = {action["id"]: action for action in report["segment_actions"]}

        self.assertEqual(summary["segments_total"], 4)
        self.assertEqual(summary["empty_translations"], 1)
        self.assertEqual(summary["missing_tts"], 2)
        self.assertEqual(summary["timing_fit_failed"], 1)
        self.assertEqual(summary["qa_flagged"], 2)
        self.assertEqual(summary["unreviewed_issues"], 1)
        self.assertEqual(actions["select-empty"]["count"], 1)
        self.assertEqual(actions["select-missing-tts"]["action"], "tts")
