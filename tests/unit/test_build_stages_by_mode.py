"""TVIDEO-128: тесты build_stages() в зависимости от translation_mode."""

from __future__ import annotations

import unittest

from translate_video.core.config import PipelineConfig, TranslationMode
from translate_video.pipeline.stages import (
    EmbedSubtitlesStage,
    ExportSubtitlesStage,
    RenderStage,
    TimingFitStage,
    TTSStage,
)
from translate_video.pipeline.utils import build_stages


def _stage_names(stages: list) -> list[str]:
    return [type(s).__name__ for s in stages]


class BuildStagesByModeTest(unittest.TestCase):
    """build_stages() должен строить разные цепочки по translation_mode."""

    def _cfg(self, mode: str) -> PipelineConfig:
        return PipelineConfig(translation_mode=mode)

    # ── Режим voiceover (дефолт) ─────────────────────────────────────────────

    def test_voiceover_has_tts_and_render(self):
        """voiceover: TTSStage и RenderStage присутствуют."""
        stages = build_stages("fake", self._cfg("voiceover"))
        names = _stage_names(stages)
        self.assertIn("TTSStage", names)
        self.assertIn("RenderStage", names)

    def test_voiceover_has_embed_no_export(self):
        """voiceover: EmbedSubtitlesStage есть, ExportSubtitlesStage нет."""
        stages = build_stages("fake", self._cfg("voiceover"))
        names = _stage_names(stages)
        self.assertIn("EmbedSubtitlesStage", names)
        self.assertNotIn("ExportSubtitlesStage", names)

    def test_voiceover_stage_count(self):
        """voiceover: ровно 8 этапов."""
        stages = build_stages("fake", self._cfg("voiceover"))
        self.assertEqual(len(stages), 8)

    # ── Режим subtitles ──────────────────────────────────────────────────────

    def test_subtitles_skips_tts(self):
        """subtitles: TTSStage и RenderStage пропускаются."""
        stages = build_stages("fake", self._cfg("subtitles"))
        names = _stage_names(stages)
        self.assertNotIn("TTSStage", names)
        self.assertNotIn("RenderStage", names)
        self.assertNotIn("TimingFitStage", names)

    def test_subtitles_has_export(self):
        """subtitles: ExportSubtitlesStage есть, EmbedSubtitlesStage нет."""
        stages = build_stages("fake", self._cfg("subtitles"))
        names = _stage_names(stages)
        self.assertIn("ExportSubtitlesStage", names)
        self.assertNotIn("EmbedSubtitlesStage", names)

    def test_subtitles_stage_count(self):
        """subtitles: ровно 5 этапов (без TTS/Timing/Render/Embed)."""
        stages = build_stages("fake", self._cfg("subtitles"))
        self.assertEqual(len(stages), 5)

    def test_subtitles_order(self):
        """subtitles: последний этап — ExportSubtitlesStage."""
        stages = build_stages("fake", self._cfg("subtitles"))
        self.assertIsInstance(stages[-1], ExportSubtitlesStage)

    # ── Режим voiceover_and_subtitles ────────────────────────────────────────

    def test_voiceover_and_subtitles_has_both(self):
        """voiceover_and_subtitles: TTS/Render + Export + Embed."""
        stages = build_stages("fake", self._cfg("voiceover_and_subtitles"))
        names = _stage_names(stages)
        self.assertIn("TTSStage", names)
        self.assertIn("RenderStage", names)
        self.assertIn("ExportSubtitlesStage", names)
        self.assertIn("EmbedSubtitlesStage", names)

    def test_voiceover_and_subtitles_stage_count(self):
        """voiceover_and_subtitles: ровно 9 этапов."""
        stages = build_stages("fake", self._cfg("voiceover_and_subtitles"))
        self.assertEqual(len(stages), 9)

    def test_voiceover_and_subtitles_export_before_embed(self):
        """voiceover_and_subtitles: ExportSubtitlesStage идёт перед EmbedSubtitlesStage."""
        stages = build_stages("fake", self._cfg("voiceover_and_subtitles"))
        names = _stage_names(stages)
        export_idx = names.index("ExportSubtitlesStage")
        embed_idx = names.index("EmbedSubtitlesStage")
        self.assertLess(export_idx, embed_idx)

    # ── Дефолт (без конфига) ─────────────────────────────────────────────────

    def test_no_config_defaults_to_voiceover(self):
        """Без project_config: TTS и Render присутствуют (voiceover — дефолт)."""
        stages = build_stages("fake", project_config=None)
        names = _stage_names(stages)
        self.assertIn("TTSStage", names)
        self.assertIn("RenderStage", names)


if __name__ == "__main__":
    unittest.main()
