"""Тесты для модуля ssml_enhance (TVIDEO-094, TVIDEO-096)."""

import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from translate_video.tts.ssml_enhance import EMOTION_OFF, enhance


def _parse_ssml(text: str) -> ET.Element:
    """Разобрать SSML-строку в XML-дерево."""
    return ET.fromstring(text)


class EmotionOffTest(unittest.TestCase):
    """Уровень 0 — возвращается исходный текст без изменений."""

    def test_plain_text_returned_unchanged(self):
        text = "Привет, мир!"
        self.assertEqual(enhance(text, EMOTION_OFF), text)

    def test_no_ssml_tags_in_output(self):
        result = enhance("Тест.", 0)
        self.assertNotIn("<speak>", result)

    def test_empty_string_returned_unchanged(self):
        self.assertEqual(enhance("", 0), "")


class SSMLStructureTest(unittest.TestCase):
    """Уровни 1-3 возвращают валидный SSML."""

    def test_level1_has_speak_root(self):
        result = enhance("Привет. Как дела?", 1)
        self.assertTrue(result.startswith("<speak>"))
        self.assertTrue(result.endswith("</speak>"))

    def test_level2_valid_xml(self):
        result = enhance("Отлично! Понял.", 2)
        # Должен парситься без исключений
        _parse_ssml(result)

    def test_level3_valid_xml(self):
        result = enhance("Внимание! Это важно. Понял?", 3)
        _parse_ssml(result)

    def test_special_chars_are_escaped(self):
        """Символы < > & в тексте должны быть экранированы."""
        result = enhance("Результат: 2 > 1 и x < 5.", 1)
        self.assertNotIn(" > 1", result)   # '>' → '&gt;'
        self.assertNotIn("x < 5", result)  # '<' → '&lt;'
        _parse_ssml(result)  # должен быть валидным XML

    def test_ampersand_escaped(self):
        result = enhance("Tom & Jerry вернулись.", 1)
        self.assertIn("&amp;", result)
        _parse_ssml(result)


class PauseTest(unittest.TestCase):
    """Паузы добавляются на знаках препинания."""

    def test_level1_has_break_after_exclamation(self):
        result = enhance("Ура! Победа.", 1)
        self.assertIn("<break", result)

    def test_level1_has_break_after_period(self):
        result = enhance("Первое. Второе.", 1)
        self.assertIn("<break", result)

    def test_level2_exclamation_has_prosody(self):
        result = enhance("Отлично! Идём дальше.", 2)
        self.assertIn("prosody", result)

    def test_level3_question_has_prosody(self):
        result = enhance("Как дела? Всё хорошо.", 3)
        self.assertIn("prosody", result)


class EmphasisTest(unittest.TestCase):
    """Ударение на ключевых словах (уровень 3)."""

    def test_level3_adds_emphasis_on_intro_word(self):
        result = enhance("Внимание! Данные изменились.", 3)
        self.assertIn("emphasis", result)

    def test_level2_does_not_add_emphasis(self):
        result = enhance("Внимание! Данные изменились.", 2)
        self.assertNotIn("emphasis", result)

    def test_level1_does_not_add_emphasis(self):
        result = enhance("Внимание! Данные изменились.", 1)
        self.assertNotIn("emphasis", result)


class EmotionLevelClampTest(unittest.TestCase):
    """Граничные значения уровня (out-of-range)."""

    def test_negative_level_treated_as_zero(self):
        """Отрицательный уровень → plain text (как 0)."""
        text = "Привет!"
        result = enhance(text, -5)
        self.assertEqual(result, text)

    def test_level_above_max_treated_as_3(self):
        """Уровень > 3 зажимается до 3 → возвращает валидный SSML."""
        result = enhance("Привет!", 99)
        self.assertTrue(result.startswith("<speak>"))
        _parse_ssml(result)


class EmptyUtteranceGuardTest(unittest.TestCase):
    """TVIDEO-096: SSML никогда не должен генерировать пустой <speak></speak>.

    Яндекс SpeechKit возвращает HTTP 400 "Empty Utterance" если отправить
    SSML без текстового содержимого. Это происходило когда:
    1. Сегмент состоял только из знаков препинания (. ! ?)
    2. _split_sentences убирал знак → escaped='' → SSML = <speak><break/></speak>
    Итог: все сегменты падали, tts_path не обновлялся, рендер брал старые mp3.
    """

    def test_punctuation_only_returns_plain_text(self):
        """Текст из одного знака ('.') должен вернуться без изменений (не SSML)."""
        result = enhance(".", 1)
        # НЕ должен быть пустым <speak></speak>
        self.assertNotIn("<speak></speak>", result)
        self.assertNotIn("<speak> </speak>", result)
        # Должен быть либо plain text, либо SSML с содержимым
        if result.startswith("<speak>"):
            inner = result[len("<speak>"):-len("</speak>")]
            self.assertTrue(inner.strip(), "inner SSML не должен быть пустым")

    def test_exclamation_only_returns_plain_text(self):
        """Текст '!' не должен давать пустой SSML."""
        result = enhance("!", 2)
        self.assertNotIn("<speak></speak>", result)

    def test_question_only_returns_plain_text(self):
        """Текст '?' не должен давать пустой SSML."""
        result = enhance("?", 3)
        self.assertNotIn("<speak></speak>", result)

    def test_empty_text_with_ssml_returns_plain(self):
        """Пустая строка при SSML > 0 не должна ломаться."""
        result = enhance("", 1)
        self.assertEqual(result, "")  # fallback на plain text

    def test_whitespace_only_text_returns_plain(self):
        """Текст из одних пробелов → plain text fallback, не пустой SSML."""
        result = enhance("   ", 2)
        self.assertNotIn("<speak></speak>", result)

    def test_normal_text_produces_valid_ssml_level1(self):
        """Нормальный текст по-прежнему производит валидный SSML."""
        result = enhance("Привет, как дела?", 1)
        self.assertTrue(result.startswith("<speak>"))
        inner = result[len("<speak>"):-len("</speak>")]
        self.assertTrue(inner.strip(), "Нормальный текст должен давать непустой SSML")

    def test_ssml_speak_content_not_only_break_tag(self):
        """SSML не должен быть <speak><break .../></speak> без текста — Яндекс отклоняет."""
        # Текст '.' → <speak><break time="..."/></speak> был старым багом
        result = enhance(".", 1)
        if result.startswith("<speak>"):
            # Допустимо только если внутри есть текстовый контент помимо тегов
            import re
            text_content = re.sub(r"<[^>]+>", "", result).strip()
            self.assertTrue(
                text_content,
                f"SSML содержит только теги без текста: {result!r}",
            )

    def test_regression_full_sentence_after_period_only(self):
        """Регрессия: один символ '.' за которым ничего нет → не падает."""
        for level in (1, 2, 3):
            with self.subTest(level=level):
                result = enhance(".", level)
                # Должен быть либо plain text, либо непустой SSML
                if result.startswith("<speak>"):
                    self.assertNotEqual(result, "<speak></speak>")
                else:
                    self.assertEqual(result, ".")


class SSMLQaFlagsResetTest(unittest.TestCase):
    """TVIDEO-096: проверяет что QA-флаги TTS сбрасываются при повторном запуске.

    Используем YandexSpeechKitTTSProvider с mock HTTP для изоляции.
    """

    def setUp(self):
        import tempfile
        from translate_video.core.config import PipelineConfig, VoiceStrategy
        from translate_video.core.schemas import SegmentStatus, VideoProject

        self._tmpdir = tempfile.TemporaryDirectory()
        self.work_dir = Path(self._tmpdir.name)
        (self.work_dir / "tts").mkdir(parents=True, exist_ok=True)

        self.cfg = PipelineConfig()
        self.cfg.voice_strategy = VoiceStrategy("single")
        self.cfg.professional_tts_provider = "yandex"
        self.cfg.professional_tts_voice = "alena"
        self.cfg.professional_tts_role = "neutral"

        self.project = VideoProject(
            id="qa_test",
            input_video=Path("test.mp4"),
            work_dir=self.work_dir,
            config=self.cfg,
        )

    def tearDown(self):
        self._tmpdir.cleanup()

    def _make_segment_with_flags(self, flags: list[str]) -> "Segment":
        import base64, json
        from translate_video.core.schemas import Segment, SegmentStatus

        s = Segment(id="seg_0", start=0.0, end=2.0, source_text="Hi")
        s.translated_text = "Привет"
        s.status = SegmentStatus.TRANSLATED
        s.qa_flags = list(flags)
        return s

    def _fake_http(self, *a, **kw) -> bytes:
        """Возвращает валидный NDJSON-ответ SpeechKit."""
        import base64, json
        chunk = {"audioChunk": {"data": base64.b64encode(b"mp3data").decode()}}
        return json.dumps(chunk).encode()

    def test_tts_flags_cleared_before_run(self):
        """tts_* флаги из предыдущего запуска удаляются в начале synthesize()."""
        from translate_video.tts.speechkit_tts import YandexSpeechKitTTSProvider

        seg = self._make_segment_with_flags([
            "tts_speechkit_error",    # ошибка прошлого запуска
            "tts_voice_alena",        # голос прошлого запуска
            "timing_fit_tight",       # флаг тайминга — ДОЛЖЕН ОСТАТЬСЯ
        ])
        self.project.segments = [seg]

        provider = YandexSpeechKitTTSProvider(
            api_key="test",
            voice_1="alena",
            voice_2="filipp",
            http_post=self._fake_http,
        )
        provider.synthesize(self.project, self.project.segments)

        flags = self.project.segments[0].qa_flags
        # TTS-флаги прошлого запуска должны быть удалены
        self.assertNotIn("tts_speechkit_error", flags)
        # Флаг тайминга должен быть сохранён
        self.assertIn("timing_fit_tight", flags)

    def test_timing_flags_preserved(self):
        """timing_fit_* и translation_* флаги сохраняются при повторной озвучке."""
        from translate_video.tts.speechkit_tts import YandexSpeechKitTTSProvider

        seg = self._make_segment_with_flags([
            "timing_fit_failed",
            "timing_fit_invalid_slot",
            "translation_rewritten_for_timing",
            "tts_speechkit_error",  # должен быть удалён
        ])
        self.project.segments = [seg]

        provider = YandexSpeechKitTTSProvider(
            api_key="test",
            voice_1="alena",
            voice_2="filipp",
            http_post=self._fake_http,
        )
        provider.synthesize(self.project, self.project.segments)

        flags = self.project.segments[0].qa_flags
        self.assertIn("timing_fit_failed", flags)
        self.assertIn("timing_fit_invalid_slot", flags)
        self.assertIn("translation_rewritten_for_timing", flags)
        self.assertNotIn("tts_speechkit_error", flags)

    def test_new_tts_flags_added_after_reset(self):
        """После сброса старых флагов добавляются новые (tts_voice_, tts_speechkit)."""
        from translate_video.tts.speechkit_tts import YandexSpeechKitTTSProvider

        seg = self._make_segment_with_flags(["tts_voice_filipp", "tts_speechkit_error"])
        self.project.segments = [seg]

        provider = YandexSpeechKitTTSProvider(
            api_key="test",
            voice_1="alena",
            voice_2="filipp",
            http_post=self._fake_http,
        )
        provider.synthesize(self.project, self.project.segments)

        flags = self.project.segments[0].qa_flags
        # Новые флаги текущего запуска добавлены
        self.assertIn("tts_voice_alena", flags)
        self.assertIn("tts_speechkit", flags)
        # Старые — удалены
        self.assertNotIn("tts_voice_filipp", flags)
        self.assertNotIn("tts_speechkit_error", flags)


if __name__ == "__main__":
    unittest.main()
