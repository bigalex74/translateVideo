"""TVIDEO-089: тесты модуля normalize.py (нормализация текста перед TTS).

Проверяет:
- 24/7 → двадцать четыре на семь
- 5/5 → пять из пяти
- % / $ / € / № конвертации
- ИИ → И И (аббревиатуры)
- Время 14:30 → четырнадцать тридцать
- Слэш между словами → пробел
- Пустой текст → пустая строка
"""
import unittest

from translate_video.tts.normalize import normalize


class NormalizeTest(unittest.TestCase):
    """TVIDEO-089: unit-тесты normalize.normalize()."""

    # ── Дроби и /7 ───────────────────────────────────────────────────────────

    def test_24_7(self):
        self.assertEqual(normalize('24/7'), 'двадцать четыре на семь')

    def test_24_7_in_sentence(self):
        r = normalize('работает 24/7 без сбоев')
        self.assertIn('двадцать четыре на семь', r)

    def test_5_5(self):
        self.assertEqual(normalize('5/5'), 'пять из пяти')

    def test_10_10(self):
        self.assertEqual(normalize('10/10'), 'десять из десяти')

    def test_3_5(self):
        self.assertEqual(normalize('3/5'), 'три из пяти')

    # ── Проценты ──────────────────────────────────────────────────────────────

    def test_percent(self):
        r = normalize('100%')
        self.assertIn('сто процентов', r)

    def test_percent_in_text(self):
        r = normalize('рост составил 50% за год')
        self.assertIn('пятьдесят процентов', r)

    # ── Валюты ────────────────────────────────────────────────────────────────

    def test_dollar_prefix(self):
        r = normalize('$100')
        self.assertIn('сто долларов', r)

    def test_dollar_suffix(self):
        r = normalize('100$')
        self.assertIn('сто долларов', r)

    def test_euro(self):
        r = normalize('€200')
        self.assertIn('двести евро', r)

    # ── Номера ────────────────────────────────────────────────────────────────

    def test_number_sign(self):
        r = normalize('№5')
        self.assertIn('номер', r)
        self.assertIn('5', r)

    # ── Время ─────────────────────────────────────────────────────────────────

    def test_time(self):
        r = normalize('14:30')
        self.assertIn('четырнадцать', r)
        self.assertIn('тридцать', r)

    # ── Аббревиатуры ──────────────────────────────────────────────────────────

    def test_ii_abbrev(self):
        r = normalize('ИИ изменил мир')
        self.assertIn('И И', r)

    def test_ii_at_end(self):
        r = normalize('Большинство используют ИИ.')
        self.assertIn('И И', r)

    # ── Слэш между словами ────────────────────────────────────────────────────

    def test_slash_between_words(self):
        r = normalize('frontend/backend')
        self.assertNotIn('/', r)
        self.assertIn('frontend', r)
        self.assertIn('backend', r)

    def test_api_slash_sdk(self):
        r = normalize('API/SDK')
        self.assertNotIn('/', r)

    # ── Граничные случаи ──────────────────────────────────────────────────────

    def test_empty_string(self):
        self.assertEqual(normalize(''), '')

    def test_plain_russian_unchanged(self):
        text = 'Мама мыла раму'
        self.assertEqual(normalize(text), text)

    def test_no_double_spaces(self):
        r = normalize('ИИ работает')
        self.assertNotIn('  ', r)


if __name__ == '__main__':
    unittest.main()
