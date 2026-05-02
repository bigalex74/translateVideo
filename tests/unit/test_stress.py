"""TVIDEO-087: тесты модуля stress.py (расстановка ударений ruaccent).

Проверяет:
- process() без ruaccent: graceful fallback → исходный текст
- process() с mock ruaccent: результат с ударениями
- process() с пустым текстом → пустая строка
- process() ошибка в акцентизаторе → fallback без исключения
- reset() сбрасывает синглтон
- use_stress=True в SpeechKit провайдере → process() вызван
- use_stress=False → process() НЕ вызван
"""
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from translate_video.tts import stress as _stress_mod
from translate_video.tts.stress import process, reset


class StressProcessTest(unittest.TestCase):
    """TVIDEO-087: тесты stress.process()."""

    def setUp(self):
        reset()

    def tearDown(self):
        reset()

    def test_empty_text_returns_empty(self):
        """Пустая строка → пустая строка без вызова модели."""
        self.assertEqual(process(""), "")
        self.assertEqual(process("   "), "   ")

    def test_fallback_if_ruaccent_unavailable(self):
        """Если ruaccent не установлен → возвращаем текст без изменений."""
        with patch.dict("sys.modules", {"ruaccent": None}):
            reset()
            result = process("Мама мыла раму")
        self.assertEqual(result, "Мама мыла раму")

    def test_returns_accented_text_via_mock(self):
        """С mock ruaccent → возвращает результат process_all."""
        mock_acc = MagicMock()
        mock_acc.process_all.return_value = "М+ама м+ыла р+аму"

        mock_ruaccent_module = MagicMock()
        mock_ruaccent_module.RUAccent.return_value = mock_acc

        reset()
        with patch.dict("sys.modules", {"ruaccent": mock_ruaccent_module}):
            _stress_mod._AVAILABLE = True
            _stress_mod._ACCENTIZER = mock_acc

            result = process("Мама мыла раму")

        self.assertEqual(result, "М+ама м+ыла р+аму")
        mock_acc.process_all.assert_called_once_with("Мама мыла раму")

    def test_accentizer_error_returns_original(self):
        """Ошибка в process_all → возвращаем исходный текст без исключения."""
        mock_acc = MagicMock()
        mock_acc.process_all.side_effect = RuntimeError("GPU out of memory")

        reset()
        _stress_mod._AVAILABLE = True
        _stress_mod._ACCENTIZER = mock_acc

        result = process("Тест ошибки")
        self.assertEqual(result, "Тест ошибки")

    def test_reset_clears_singleton(self):
        """reset() обнуляет _ACCENTIZER и _AVAILABLE."""
        _stress_mod._AVAILABLE = True
        _stress_mod._ACCENTIZER = MagicMock()

        reset()

        self.assertIsNone(_stress_mod._ACCENTIZER)
        self.assertIsNone(_stress_mod._AVAILABLE)


class StressIntegrationWithSpeechKitTest(unittest.TestCase):
    """TVIDEO-087: интеграция use_stress с YandexSpeechKitTTSProvider."""

    def _make_provider(self, use_stress: bool):
        from translate_video.tts.speechkit_tts import YandexSpeechKitTTSProvider
        return YandexSpeechKitTTSProvider(
            api_key="test_key",
            voice_1="alena",
            voice_2="filipp",
            use_stress=use_stress,
            http_post=lambda *a, **kw: b"mp3",
        )

    def _make_project(self):
        import tempfile
        from translate_video.core.config import PipelineConfig
        from translate_video.core.schemas import VideoProject
        tmpdir = tempfile.mkdtemp()
        cfg = PipelineConfig()
        cfg.professional_tts_provider = "yandex"
        cfg.voice_strategy = "single"  # type: ignore[assignment]
        project = VideoProject(
            id="stress_test",
            input_video=Path("v.mp4"),
            work_dir=Path(tmpdir),
            config=cfg,
        )
        (Path(tmpdir) / "tts").mkdir(parents=True, exist_ok=True)
        return project

    def _make_segment(self, text: str):
        from translate_video.core.schemas import Segment, SegmentStatus
        s = Segment(id="seg_0", start=0, end=2, source_text="Test")
        s.translated_text = text
        s.status = SegmentStatus.TRANSLATED
        return s

    def test_use_stress_true_calls_process(self):
        """use_stress=True → stress.process() вызывается до синтеза."""
        provider = self._make_provider(use_stress=True)
        project = self._make_project()
        seg = self._make_segment("Мама мыла раму")

        with patch("translate_video.tts.speechkit_tts._stress") as mock_stress:
            mock_stress.process.return_value = "М+ама м+ыла р+аму"
            project.segments = [seg]
            provider.synthesize(project, [seg])

        mock_stress.process.assert_called_once_with("Мама мыла раму")

    def test_use_stress_false_skips_process(self):
        """use_stress=False → stress.process() НЕ вызывается."""
        provider = self._make_provider(use_stress=False)
        project = self._make_project()
        seg = self._make_segment("Мама мыла раму")

        with patch("translate_video.tts.speechkit_tts._stress") as mock_stress:
            mock_stress.process.return_value = "М+ама м+ыла р+аму"
            project.segments = [seg]
            provider.synthesize(project, [seg])

        mock_stress.process.assert_not_called()


if __name__ == "__main__":
    unittest.main()
