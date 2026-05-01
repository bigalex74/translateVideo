"""Тесты адаптивного rate TTS (TVIDEO-040b).

Покрывает:
- _compute_rate: правильный расчёт rate при overflow
- _fmt_rate: форматирование строки rate
- EdgeTTSProvider.synthesize():
  - аудио умещается → rate не меняется
  - аудио не умещается → вычисляем rate и переозвучиваем
  - ffprobe недоступен → синтез один раз, без адаптации
  - rate ограничивается до tts_max_rate
  - qa_flag tts_rate_adapted ставится при адаптации
"""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from translate_video.tts.legacy import EdgeTTSProvider, _compute_rate, _fmt_rate


# ─── _compute_rate ────────────────────────────────────────────────────────────

class TestComputeRate(unittest.TestCase):
    """TVIDEO-040b: _compute_rate — расчёт нужного rate."""

    def test_no_overflow_returns_base(self):
        """Аудио = слот → нужен только base_rate."""
        # duration <= slot → ratio = 1.0 → extra = 0 → base_rate
        result = _compute_rate(duration=3.0, slot=3.0, base_rate=5, max_rate=40)
        self.assertEqual(result, 5)

    def test_20_percent_overflow(self):
        """Аудио на 20% длиннее → rate += 20."""
        # duration=3.6, slot=3.0, ratio=1.2, extra=20, rate=5+20=25
        result = _compute_rate(duration=3.6, slot=3.0, base_rate=5, max_rate=40)
        self.assertEqual(result, 25)

    def test_capped_at_max_rate(self):
        """Очень длинное аудио → rate ограничивается до max_rate."""
        # duration=6.0, slot=2.0, ratio=3.0, extra=200, base+200=205 → cap 40
        result = _compute_rate(duration=6.0, slot=2.0, base_rate=5, max_rate=40)
        self.assertEqual(result, 40)

    def test_rounds_up(self):
        """Дробное превышение → округляем вверх."""
        # duration=3.1, slot=3.0, ratio=1.033..., extra=ceil(3.33%)=4 → 5+4=9
        result = _compute_rate(duration=3.1, slot=3.0, base_rate=5, max_rate=40)
        self.assertGreater(result, 5)

    def test_small_overflow_still_positive(self):
        """1% превышения → rate немного больше base."""
        result = _compute_rate(duration=3.03, slot=3.0, base_rate=5, max_rate=40)
        self.assertGreaterEqual(result, 5)


# ─── _fmt_rate ────────────────────────────────────────────────────────────────

class TestFmtRate(unittest.TestCase):
    """TVIDEO-040b: _fmt_rate — форматирование строки rate."""

    def test_positive_rate(self):
        self.assertEqual(_fmt_rate(15), "+15%")

    def test_zero_rate(self):
        self.assertEqual(_fmt_rate(0), "+0%")

    def test_negative_rate(self):
        self.assertEqual(_fmt_rate(-10), "-10%")


# ─── EdgeTTSProvider.synthesize ───────────────────────────────────────────────

class TestEdgeTTSProviderAdaptive(unittest.TestCase):
    """TVIDEO-040b: EdgeTTSProvider.synthesize() с адаптивным rate."""

    def _make_segment(self, start=0.0, end=3.0, text="Привет мир."):
        from translate_video.core.schemas import Segment
        return Segment(start=start, end=end, source_text="Hello.", translated_text=text)

    def _make_project(self, tmp_dir, base_rate=5, max_rate=40, slack=1.03):
        from translate_video.core.config import PipelineConfig
        project = MagicMock()
        project.config = PipelineConfig(
            tts_base_rate=base_rate,
            tts_max_rate=max_rate,
            tts_rate_slack=slack,
        )
        project.config.target_language = "ru"
        project.work_dir = tmp_dir
        return project

    def test_no_adaptation_when_audio_fits(self):
        """Аудио умещается в слот → синтез один раз, rate не меняется."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "tts").mkdir()
            seg = self._make_segment(start=0.0, end=5.0)
            project = self._make_project(tmp)
            synth_rates = []

            def fake_comm(text, voice, rate=None):
                synth_rates.append(rate)
                m = MagicMock()
                m.save = MagicMock(return_value=None)
                return m

            provider = EdgeTTSProvider(
                communicate_factory=fake_comm,
                async_runner=lambda coro: None,
            )
            with patch("translate_video.tts.legacy.get_audio_duration", return_value=2.0):
                provider.synthesize(project, [seg])

            self.assertEqual(len(synth_rates), 1)
            self.assertEqual(synth_rates[0], "+5%")
            self.assertNotIn("tts_rate_adapted", seg.qa_flags)

    def test_adaptation_triggered_on_overflow(self):
        """Аудио не умещается → ускоряем, переозвучиваем."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "tts").mkdir()
            seg = self._make_segment(start=0.0, end=2.0)  # слот 2с
            project = self._make_project(tmp, base_rate=5, max_rate=40, slack=1.03)
            synth_rates = []

            def fake_comm(text, voice, rate=None):
                synth_rates.append(rate)
                m = MagicMock()
                m.save = MagicMock(return_value=None)
                return m

            provider = EdgeTTSProvider(
                communicate_factory=fake_comm,
                async_runner=lambda coro: None,
            )
            # 3.0с > 2.0 * 1.03 = 2.06с → overflow
            with patch("translate_video.tts.legacy.get_audio_duration", return_value=3.0):
                provider.synthesize(project, [seg])

            self.assertEqual(len(synth_rates), 2)
            self.assertEqual(synth_rates[0], "+5%")   # первичный
            # Второй rate должен быть больше
            second_rate = int(synth_rates[1].strip("+%"))
            self.assertGreater(second_rate, 5)
            self.assertIn("tts_rate_adapted", seg.qa_flags)

    def test_rate_capped_at_max(self):
        """Очень длинное аудио → rate не превышает tts_max_rate."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "tts").mkdir()
            seg = self._make_segment(start=0.0, end=1.0)  # слот 1с
            project = self._make_project(tmp, base_rate=5, max_rate=40, slack=1.03)
            synth_rates = []

            def fake_comm(text, voice, rate=None):
                synth_rates.append(rate)
                m = MagicMock()
                m.save = MagicMock(return_value=None)
                return m

            provider = EdgeTTSProvider(
                communicate_factory=fake_comm,
                async_runner=lambda coro: None,
            )
            # 10с >> 1с → rate должен зафиксироваться на max=40
            with patch("translate_video.tts.legacy.get_audio_duration", return_value=10.0):
                provider.synthesize(project, [seg])

            self.assertEqual(len(synth_rates), 2)
            self.assertEqual(synth_rates[1], "+40%")

    def test_no_adaptation_when_ffprobe_unavailable(self):
        """ffprobe недоступен → синтез один раз."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "tts").mkdir()
            seg = self._make_segment()
            project = self._make_project(tmp)
            synth_count = [0]

            def fake_comm(text, voice, rate=None):
                synth_count[0] += 1
                m = MagicMock()
                m.save = MagicMock(return_value=None)
                return m

            provider = EdgeTTSProvider(
                communicate_factory=fake_comm,
                async_runner=lambda coro: None,
            )
            with patch("translate_video.tts.legacy.get_audio_duration", return_value=None):
                provider.synthesize(project, [seg])

            self.assertEqual(synth_count[0], 1)
            self.assertNotIn("tts_rate_adapted", seg.qa_flags)

    def test_empty_text_skipped(self):
        """Сегмент с пустым translated_text пропускается."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "tts").mkdir()
            seg = self._make_segment(text="")
            seg.translated_text = ""
            project = self._make_project(tmp)
            synth_count = [0]

            def fake_comm(text, voice, rate=None):
                synth_count[0] += 1
                m = MagicMock()
                m.save = MagicMock(return_value=None)
                return m

            provider = EdgeTTSProvider(
                communicate_factory=fake_comm,
                async_runner=lambda coro: None,
            )
            with patch("translate_video.tts.legacy.get_audio_duration", return_value=None):
                provider.synthesize(project, [seg])

            self.assertEqual(synth_count[0], 0)

    def test_overflow_after_rate_is_reported(self):
        """Если ускоренная озвучка всё равно длинная, ставится QA-флаг overflow."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "tts").mkdir()
            seg = self._make_segment(start=0.0, end=2.0)
            project = self._make_project(tmp, base_rate=5, max_rate=40, slack=1.03)

            def fake_comm(text, voice, rate=None):
                m = MagicMock()
                m.save = MagicMock(return_value=None)
                return m

            provider = EdgeTTSProvider(
                communicate_factory=fake_comm,
                async_runner=lambda coro: None,
            )
            with patch("translate_video.tts.legacy.get_audio_duration", side_effect=[4.0, 3.0]):
                provider.synthesize(project, [seg])

            self.assertIn("tts_rate_adapted", seg.qa_flags)
            self.assertIn("tts_overflow_after_rate", seg.qa_flags)

    def test_zero_duration_slot_does_not_divide_by_zero(self):
        """Нулевой слот не должен ломать TTS-этап делением на ноль."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "tts").mkdir()
            seg = self._make_segment(start=1.0, end=1.0)
            project = self._make_project(tmp)

            def fake_comm(text, voice, rate=None):
                m = MagicMock()
                m.save = MagicMock(return_value=None)
                return m

            provider = EdgeTTSProvider(
                communicate_factory=fake_comm,
                async_runner=lambda coro: None,
            )
            with patch("translate_video.tts.legacy.get_audio_duration") as duration_probe:
                provider.synthesize(project, [seg])

            duration_probe.assert_not_called()
            self.assertIn("tts_invalid_slot", seg.qa_flags)


if __name__ == "__main__":
    unittest.main()
