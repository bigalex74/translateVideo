"""Тесты LLM-сжатия TTS (TVIDEO-037).

Покрывает:
- get_audio_duration: ffprobe OK, файл не найден, некорректный вывод
- compress_via_llm: успешное сжатие, LLM не сократил, Ollama недоступен
- EdgeTTSProvider.synthesize(): без переполнения, с переполнением и сжатием,
  LLM недоступен → синтез без изменений
"""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import MagicMock, call, patch


# ─── get_audio_duration ───────────────────────────────────────────────────────


class TestGetAudioDuration(unittest.TestCase):
    """TVIDEO-037: get_audio_duration — измерение через ffprobe."""

    def _run(self, stdout="", returncode=0):
        from translate_video.tts.compress import get_audio_duration
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout=stdout, stderr="", returncode=returncode
            )
            return get_audio_duration(Path("/tmp/test.mp3"))

    def test_returns_duration_from_ffprobe(self):
        """ffprobe вернул duration=4.5 → 4.5."""
        result = self._run("duration=4.500000\n")
        self.assertAlmostEqual(result, 4.5)

    def test_returns_none_on_empty_output(self):
        """ffprobe ничего не вернул → None."""
        result = self._run("")
        self.assertIsNone(result)

    def test_returns_none_when_ffprobe_not_found(self):
        """ffprobe не установлен → None, без исключения."""
        from translate_video.tts.compress import get_audio_duration
        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = get_audio_duration(Path("/tmp/test.mp3"))
        self.assertIsNone(result)

    def test_returns_none_on_timeout(self):
        """ffprobe завис → None, без исключения."""
        import subprocess
        from translate_video.tts.compress import get_audio_duration
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("ffprobe", 10)):
            result = get_audio_duration(Path("/tmp/test.mp3"))
        self.assertIsNone(result)


# ─── compress_via_llm ─────────────────────────────────────────────────────────


class TestCompressViaLlm(unittest.TestCase):
    """TVIDEO-037: compress_via_llm — запрос к Ollama."""

    def _call(self, response_text: str, status_code: int = 200):
        from translate_video.tts.compress import compress_via_llm
        with patch("requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = status_code
            mock_resp.json.return_value = {"response": response_text}
            mock_resp.raise_for_status = MagicMock()
            mock_post.return_value = mock_resp
            return compress_via_llm(
                text="Это длинный переведённый текст который нужно сократить.",
                current_sec=4.0,
                target_sec=2.5,
                model="qwen3.5:9b",
                ollama_url="http://127.0.0.1:11434",
            )

    def test_returns_compressed_text(self):
        """Ollama вернул более короткий текст → возвращаем его."""
        result = self._call("Короткий текст.")
        self.assertEqual(result, "Короткий текст.")

    def test_returns_none_if_not_shorter(self):
        """LLM вернул текст той же или большей длины → None."""
        long_response = "Это очень длинный ответ который не стал короче ни на символ."
        result = self._call(long_response)
        self.assertIsNone(result)

    def test_returns_none_on_empty_response(self):
        """LLM вернул пустой ответ → None."""
        result = self._call("")
        self.assertIsNone(result)

    def test_returns_none_on_network_error(self):
        """Ollama недоступен → None, без исключения."""
        import requests
        from translate_video.tts.compress import compress_via_llm
        with patch("requests.post", side_effect=requests.ConnectionError("refused")):
            result = compress_via_llm("текст", 4.0, 2.5, "qwen3.5:9b", "http://127.0.0.1:11434")
        self.assertIsNone(result)

    def test_strips_surrounding_quotes(self):
        """LLM добавил кавычки вокруг текста → убираем."""
        result = self._call('"Короткий."')
        self.assertEqual(result, "Короткий.")


# ─── EdgeTTSProvider с compress loop ─────────────────────────────────────────


class TestEdgeTTSProviderCompress(unittest.TestCase):
    """TVIDEO-037: EdgeTTSProvider.synthesize() с LLM-loop."""

    def _make_segment(self, start=0.0, end=3.0, text="Привет мир."):
        from translate_video.core.schemas import Segment
        return Segment(start=start, end=end, source_text="Hello world.", translated_text=text)

    def _make_project(self, tmp_dir, compress_slack=1.05, max_retries=2):
        """Фейковый project с конфигом."""
        from translate_video.core.config import PipelineConfig
        project = MagicMock()
        project.config = PipelineConfig(
            compress_slack=compress_slack,
            compress_max_retries=max_retries,
            compress_llm_url="http://127.0.0.1:11434",
            compress_llm_model="qwen3.5:9b",
        )
        project.config.target_language = "ru"
        project.work_dir = tmp_dir
        return project

    def test_no_compression_when_fits(self):
        """TTS укладывается в слот → LLM не вызывается."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "tts").mkdir()
            seg = self._make_segment(start=0.0, end=5.0, text="Короткий текст.")
            project = self._make_project(tmp)
            synth_texts = []

            def fake_communicate(text, voice, rate=None):
                synth_texts.append(text)
                m = MagicMock()
                m.save = MagicMock(return_value=None)
                return m

            from translate_video.tts.legacy import EdgeTTSProvider
            provider = EdgeTTSProvider(
                communicate_factory=fake_communicate,
                async_runner=lambda coro: None,
            )

            with patch("translate_video.tts.legacy.get_audio_duration", return_value=2.0), \
                 patch("translate_video.tts.legacy.compress_via_llm") as mock_llm:
                provider.synthesize(project, [seg])

            mock_llm.assert_not_called()
            self.assertEqual(len(synth_texts), 1)
            self.assertEqual(seg.tts_text, "")  # не изменён

    def test_compression_triggered_on_overflow(self):
        """TTS не укладывается → LLM вызывается, текст сжимается, re-synth."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "tts").mkdir()
            seg = self._make_segment(
                start=0.0, end=2.0,
                text="Очень длинный текст который явно не уложится в два секунды.",
            )
            project = self._make_project(tmp, compress_slack=1.05, max_retries=2)
            synth_texts = []

            def fake_communicate(text, voice, rate=None):
                synth_texts.append(text)
                m = MagicMock()
                m.save = MagicMock(return_value=None)
                return m

            from translate_video.tts.legacy import EdgeTTSProvider
            provider = EdgeTTSProvider(
                communicate_factory=fake_communicate,
                async_runner=lambda coro: None,
            )

            # Первое измерение: 3.5с > 2.0 * 1.05 = 2.1с → compress
            # Второе измерение (после сжатия): 1.8с → OK
            durations = [3.5, 1.8]
            with patch("translate_video.tts.legacy.get_audio_duration", side_effect=durations), \
                 patch("translate_video.tts.legacy.compress_via_llm", return_value="Короткий.") as mock_llm:
                provider.synthesize(project, [seg])

            mock_llm.assert_called_once()
            self.assertEqual(len(synth_texts), 2)  # синтез + ре-синтез
            self.assertEqual(synth_texts[1], "Короткий.")
            self.assertEqual(seg.tts_text, "Короткий.")
            self.assertIn("tts_llm_compressed", seg.qa_flags)

    def test_no_resynth_when_llm_returns_none(self):
        """LLM недоступен → синтез один раз, tts_text пустой."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "tts").mkdir()
            seg = self._make_segment(start=0.0, end=1.0, text="Длинный текст сегмент.")
            project = self._make_project(tmp)
            synth_count = [0]

            def fake_communicate(text, voice, rate=None):
                synth_count[0] += 1
                m = MagicMock()
                m.save = MagicMock(return_value=None)
                return m

            from translate_video.tts.legacy import EdgeTTSProvider
            provider = EdgeTTSProvider(
                communicate_factory=fake_communicate,
                async_runner=lambda coro: None,
            )

            with patch("translate_video.tts.legacy.get_audio_duration", return_value=3.0), \
                 patch("translate_video.tts.legacy.compress_via_llm", return_value=None):
                provider.synthesize(project, [seg])

            self.assertEqual(synth_count[0], 1)  # только первичный
            self.assertEqual(seg.tts_text, "")
            self.assertNotIn("tts_llm_compressed", seg.qa_flags)

    def test_duration_none_skips_compress(self):
        """ffprobe недоступен → compress не запускается."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "tts").mkdir()
            seg = self._make_segment()
            project = self._make_project(tmp)

            def fake_communicate(text, voice, rate=None):
                m = MagicMock()
                m.save = MagicMock(return_value=None)
                return m

            from translate_video.tts.legacy import EdgeTTSProvider
            provider = EdgeTTSProvider(
                communicate_factory=fake_communicate,
                async_runner=lambda coro: None,
            )

            with patch("translate_video.tts.legacy.get_audio_duration", return_value=None), \
                 patch("translate_video.tts.legacy.compress_via_llm") as mock_llm:
                provider.synthesize(project, [seg])

            mock_llm.assert_not_called()


if __name__ == "__main__":
    unittest.main()
