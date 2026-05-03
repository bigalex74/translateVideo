"""Юнит-тесты для yo_restore и QA-флага tts_text_too_long."""
import unittest
from pathlib import Path

from translate_video.tts.yo_restore import restore_yo
from translate_video.tts.normalize import normalize


class YoRestoreTest(unittest.TestCase):
    """Тесты восстановления «ё» из «е»."""

    def test_basic_verbs(self):
        """Часто встречающиеся глаголы."""
        self.assertEqual(restore_yo("Кот пошел в лес."), "Кот пошёл в лес.")
        self.assertEqual(restore_yo("Он нашел ключ."), "Он нашёл ключ.")
        self.assertEqual(restore_yo("Она пришла."), "Она пришла.")   # нет ё
        self.assertEqual(restore_yo("Идет дождь."), "Идёт дождь.")
        self.assertEqual(restore_yo("Она живет здесь."), "Она живёт здесь.")
        self.assertEqual(restore_yo("Вода льет."), "Вода льёт.")

    def test_pronouns_and_particles(self):
        """Местоимения и частицы."""
        self.assertEqual(restore_yo("Все готово."), "Всё готово.")
        self.assertEqual(restore_yo("Еще раз."), "Ещё раз.")
        self.assertEqual(restore_yo("Её книга."), "Её книга.")
        self.assertEqual(restore_yo("Мое мнение."), "Моё мнение.")
        self.assertEqual(restore_yo("Свое дело."), "Своё дело.")

    def test_adjectives(self):
        """Прилагательные."""
        self.assertEqual(restore_yo("Зеленый лед."), "Зелёный лёд.")
        self.assertEqual(restore_yo("Черный мед."), "Чёрный мёд.")
        self.assertEqual(restore_yo("Желтый тяжелый груз."), "Жёлтый тяжёлый груз.")

    def test_nouns(self):
        """Существительные."""
        self.assertEqual(restore_yo("Приятный прием."), "Приятный приём.")
        self.assertEqual(restore_yo("Большой объем."), "Большой объём.")
        self.assertEqual(restore_yo("Подъем в горы."), "Подъём в горы.")
        self.assertEqual(restore_yo("Слышен шепот."), "Слышен шёпот.")

    def test_no_change_words(self):
        """Слова без ё — не должны меняться."""
        text = "Знает, может, имеет, хочет, говорит."
        self.assertEqual(restore_yo(text), text)

    def test_case_insensitive(self):
        """Работает для заглавных букв."""
        self.assertEqual(restore_yo("Все готово."), "Всё готово.")
        self.assertEqual(restore_yo("ВСЕ готово."), "ВСЁ готово.")

    def test_empty_text(self):
        """Пустой текст — без изменений."""
        self.assertEqual(restore_yo(""), "")
        self.assertEqual(restore_yo("   "), "   ")

    def test_already_correct_yo(self):
        """Уже правильный «ё» — не меняется."""
        text = "Всё идёт хорошо, зелёный лёд тает."
        self.assertEqual(restore_yo(text), text)


class NormalizeYoIntegrationTest(unittest.TestCase):
    """Интеграция yo_restore в normalize()."""

    def test_normalize_includes_yo(self):
        """normalize() восстанавливает ё и нормализует числа."""
        result = normalize("Зеленый объем составляет 100%, идет работа.")
        self.assertIn("Зелёный", result)
        self.assertIn("объём", result)
        self.assertIn("идёт", result)
        self.assertIn("сто процентов", result)

    def test_normalize_yo_before_numbers(self):
        """ё восстанавливается и не ломает нормализацию чисел."""
        result = normalize("Прием 5/5 идет хорошо.")
        self.assertIn("приём", result.lower())
        self.assertIn("пяти", result)
        self.assertIn("идёт", result)


class TtsTextTooLongQaTest(unittest.TestCase):
    """Тест QA-флага tts_text_too_long при превышении 220 символов."""

    def setUp(self):
        import tempfile
        self._tmpdir = tempfile.TemporaryDirectory()
        self.work_dir = Path(self._tmpdir.name)
        (self.work_dir / "tts").mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self._tmpdir.cleanup()

    def _make_provider(self, post_fn):
        from translate_video.tts.speechkit_tts import YandexSpeechKitTTSProvider
        return YandexSpeechKitTTSProvider(
            api_key="test",
            voice_1="alena",
            voice_2="filipp",
            emotion_level=0,
            http_post=post_fn,
            use_stress=False,  # не нужен для теста длины
        )

    def _make_project_and_seg(self, text: str):
        from tests.unit.test_speechkit_tts import _make_project, _make_segment, _make_streaming_response
        project = _make_project(self.work_dir)
        seg = _make_segment(0, text)
        project.segments = [seg]
        return project, seg

    def test_short_text_no_flag(self):
        """Текст < 220 символов — флага нет."""
        from tests.unit.test_speechkit_tts import _make_streaming_response
        def post(url, payload, **kw): return _make_streaming_response(b"audio")
        provider = self._make_provider(post)
        short_text = "Короткая фраза."
        project, seg = self._make_project_and_seg(short_text)
        provider.synthesize(project, project.segments)
        self.assertNotIn("tts_text_too_long", seg.qa_flags,
            "Короткий текст не должен получать флаг tts_text_too_long")

    def test_long_text_gets_flag(self):
        """Текст > 220 символов — получает флаг tts_text_too_long."""
        from tests.unit.test_speechkit_tts import _make_streaming_response
        def post(url, payload, **kw): return _make_streaming_response(b"audio")
        provider = self._make_provider(post)
        # 230 символов русского текста
        long_text = "А" * 230
        project, seg = self._make_project_and_seg(long_text)
        provider.synthesize(project, project.segments)
        self.assertIn("tts_text_too_long", seg.qa_flags,
            "Длинный текст (>220 символов) должен получать флаг tts_text_too_long")

    def test_boundary_exactly_220_no_flag(self):
        """Текст ровно 220 символов — флага нет (граничный случай)."""
        from tests.unit.test_speechkit_tts import _make_streaming_response
        def post(url, payload, **kw): return _make_streaming_response(b"audio")
        provider = self._make_provider(post)
        boundary_text = "А" * 220
        project, seg = self._make_project_and_seg(boundary_text)
        provider.synthesize(project, project.segments)
        self.assertNotIn("tts_text_too_long", seg.qa_flags,
            "Текст ровно 220 символов не должен получать флаг")


if __name__ == "__main__":
    unittest.main()
