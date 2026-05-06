"""Unit-тесты tts/compress.py — get_audio_duration и compress_via_llm.

Покрывает: ffprobe success/fail, LLM успех/пустой ответ/не сократил/ошибка сети.
"""

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from translate_video.tts.compress import compress_via_llm, get_audio_duration


class GetAudioDurationTest(unittest.TestCase):
    """Тесты get_audio_duration через ffprobe."""

    def test_success_returns_float(self):
        """При успешном вызове ffprobe возвращается float."""
        mock_result = MagicMock()
        mock_result.stdout = "duration=12.345\n"
        with patch("translate_video.tts.compress.subprocess.run", return_value=mock_result):
            result = get_audio_duration(Path("/fake/audio.mp3"))
        self.assertAlmostEqual(result, 12.345)

    def test_ffprobe_not_found_returns_none(self):
        """Если ffprobe не установлен — возвращается None."""
        with patch("translate_video.tts.compress.subprocess.run",
                   side_effect=FileNotFoundError("ffprobe not found")):
            result = get_audio_duration(Path("/fake/audio.mp3"))
        self.assertIsNone(result)

    def test_timeout_returns_none(self):
        """При таймауте ffprobe — возвращается None."""
        import subprocess
        with patch("translate_video.tts.compress.subprocess.run",
                   side_effect=subprocess.TimeoutExpired("ffprobe", 10)):
            result = get_audio_duration(Path("/fake/audio.mp3"))
        self.assertIsNone(result)

    def test_no_duration_line_returns_none(self):
        """Если в выводе нет строки duration= — возвращается None."""
        mock_result = MagicMock()
        mock_result.stdout = "some_other_key=12.3\n"
        with patch("translate_video.tts.compress.subprocess.run", return_value=mock_result):
            result = get_audio_duration(Path("/fake/audio.mp3"))
        self.assertIsNone(result)

    def test_invalid_float_returns_none(self):
        """Некорректное значение duration — возвращается None."""
        mock_result = MagicMock()
        mock_result.stdout = "duration=not_a_number\n"
        with patch("translate_video.tts.compress.subprocess.run", return_value=mock_result):
            result = get_audio_duration(Path("/fake/audio.mp3"))
        self.assertIsNone(result)

    def test_multiline_output_finds_duration(self):
        """Из многострочного вывода ffprobe парсируется duration."""
        mock_result = MagicMock()
        mock_result.stdout = "bit_rate=128000\nduration=60.5\naudio_codec=mp3\n"
        with patch("translate_video.tts.compress.subprocess.run", return_value=mock_result):
            result = get_audio_duration(Path("/fake/audio.mp3"))
        self.assertAlmostEqual(result, 60.5)


class CompressViaLlmTest(unittest.TestCase):
    """Тесты compress_via_llm."""

    _URL = "http://localhost:11434"
    _MODEL = "qwen2.5:3b"

    def _mock_post(self, response_text: str):
        """Хелпер: мокаем requests.post с заданным текстом ответа."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"response": response_text}
        mock_resp.raise_for_status = MagicMock()
        return patch("translate_video.tts.compress.requests.post", return_value=mock_resp)

    def test_success_returns_shorter_text(self):
        """Успешный ответ LLM с коротким текстом — возвращается."""
        original = "Это длинный текст который нужно сократить"
        compressed = "Краткий текст"
        with self._mock_post(compressed):
            result = compress_via_llm(original, 5.0, 3.0, self._MODEL, self._URL)
        self.assertEqual(result, compressed)

    def test_empty_response_returns_none(self):
        """Пустой ответ LLM — возвращается None."""
        with self._mock_post(""):
            result = compress_via_llm("Текст для сжатия", 5.0, 3.0, self._MODEL, self._URL)
        self.assertIsNone(result)

    def test_whitespace_only_returns_none(self):
        """Ответ из пробелов — возвращается None."""
        with self._mock_post("   "):
            result = compress_via_llm("Текст", 5.0, 3.0, self._MODEL, self._URL)
        self.assertIsNone(result)

    def test_longer_result_returns_none(self):
        """LLM вернул более длинный текст — возвращается None (не помог)."""
        original = "Коротко"
        longer = "Это значительно более длинный текст чем оригинал и не должен приниматься"
        with self._mock_post(longer):
            result = compress_via_llm(original, 5.0, 3.0, self._MODEL, self._URL)
        self.assertIsNone(result)

    def test_same_length_returns_none(self):
        """LLM вернул текст той же длины — возвращается None."""
        original = "АБВГДЕЖ"
        same = "ЁЖЗИЙКЛ"
        self.assertEqual(len(original), len(same))
        with self._mock_post(same):
            result = compress_via_llm(original, 5.0, 3.0, self._MODEL, self._URL)
        self.assertIsNone(result)

    def test_network_error_returns_none(self):
        """Сетевая ошибка — не бросает, возвращает None."""
        import requests as req
        with patch("translate_video.tts.compress.requests.post",
                   side_effect=req.ConnectionError("refused")):
            result = compress_via_llm("Текст", 5.0, 3.0, self._MODEL, self._URL)
        self.assertIsNone(result)

    def test_unexpected_exception_returns_none(self):
        """Непредвиденная ошибка — не бросает, возвращает None."""
        with patch("translate_video.tts.compress.requests.post",
                   side_effect=RuntimeError("unexpected")):
            result = compress_via_llm("Текст", 5.0, 3.0, self._MODEL, self._URL)
        self.assertIsNone(result)

    def test_strips_quotes_from_response(self):
        """Кавычки в ответе LLM убираются."""
        original = "Длинный текст для теста удаления кавычек"
        compressed = '"Краткий"'  # LLM завернул в кавычки
        with self._mock_post(compressed):
            result = compress_via_llm(original, 5.0, 3.0, self._MODEL, self._URL)
        self.assertEqual(result, "Краткий")

    def test_prompt_uses_correct_values(self):
        """Промпт включает target_sec и current_sec."""
        with self._mock_post("Краткий ответ") as mock_post:
            compress_via_llm("Длинный текст для проверки", 4.0, 7.0, self._MODEL, self._URL)
        call_kwargs = mock_post.call_args[1]
        prompt = call_kwargs["json"]["prompt"]
        self.assertIn("4.0", prompt)
        self.assertIn("7.0", prompt)


if __name__ == "__main__":
    unittest.main()
