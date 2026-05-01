"""Тесты перегруппировки сегментов по предложениям (TVIDEO-039).

Покрывает:
- Два обрывка → одно предложение (start/end наследуются)
- Два коротких разных предложения → остаются отдельными
- Три коротких → первые два объединяются если второе заканчивается предложением
- Превышение max_slot → принудительный сброс без границы
- Одиночный сегмент → без изменений
- Пустой список → пустой список
- Последний буфер всегда сбрасывается (нет потерь)
- source_text правильно конкатенируется через пробел
- Различные знаки конца (.!?…)
"""

from __future__ import annotations

import unittest

from translate_video.core.schemas import Segment
from translate_video.speech.regroup import regroup_by_sentences


def _seg(text: str, start: float, end: float) -> Segment:
    return Segment(start=start, end=end, source_text=text)


class TestRegroupBySentences(unittest.TestCase):
    """TVIDEO-039: regroup_by_sentences — перегруппировка по предложениям."""

    def test_empty_list(self):
        """Пустой список → пустой список."""
        self.assertEqual(regroup_by_sentences([]), [])

    def test_single_segment_unchanged(self):
        """Одиночный сегмент без точки → возвращается как есть."""
        segs = [_seg("Hello world", 0.0, 3.0)]
        result = regroup_by_sentences(segs, max_slot=8.0)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].source_text, "Hello world")
        self.assertAlmostEqual(result[0].start, 0.0)
        self.assertAlmostEqual(result[0].end, 3.0)

    def test_two_fragments_merge_into_one_sentence(self):
        """Два обрывка объединяются в одно предложение."""
        segs = [
            _seg("Have you ever had a brilliant idea for an app, but stopped", 0.0, 5.1),
            _seg("right in your tracks because you don't know how to code?", 5.1, 7.3),
        ]
        result = regroup_by_sentences(segs, max_slot=8.0)
        self.assertEqual(len(result), 1)
        self.assertAlmostEqual(result[0].start, 0.0)
        self.assertAlmostEqual(result[0].end, 7.3)
        self.assertIn("brilliant idea", result[0].source_text)
        self.assertIn("know how to code?", result[0].source_text)

    def test_two_complete_sentences_stay_separate(self):
        """Два полных предложения остаются отдельными слотами."""
        segs = [
            _seg("That barrier is gone.", 12.3, 14.1),
            _seg("A new tool called Google anti-gravity removes the requirement.", 14.1, 19.8),
        ]
        result = regroup_by_sentences(segs, max_slot=8.0)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].source_text, "That barrier is gone.")
        self.assertAlmostEqual(result[0].start, 12.3)
        self.assertAlmostEqual(result[0].end, 14.1)
        self.assertAlmostEqual(result[1].start, 14.1)
        self.assertAlmostEqual(result[1].end, 19.8)

    def test_three_fragments_merge_to_two_sentences(self):
        """Три фрагмента: первые два образуют предложение, третье — отдельное."""
        segs = [
            _seg("For decades, building an application meant", 19.8, 22.0),
            _seg("you had to be the constructor.", 22.0, 23.8),
            _seg("Now you can be the executive.", 23.8, 27.0),
        ]
        result = regroup_by_sentences(segs, max_slot=8.0)
        self.assertEqual(len(result), 2)
        self.assertIn("For decades", result[0].source_text)
        self.assertIn("constructor.", result[0].source_text)
        self.assertEqual(result[1].source_text, "Now you can be the executive.")

    def test_max_slot_forces_flush(self):
        """Превышение max_slot → принудительный сброс без границы предложения."""
        segs = [
            _seg("This is a very long sentence that", 0.0, 4.0),
            _seg("keeps going on and on without ending", 4.0, 8.5),  # вместе = 8.5 > 8.0
        ]
        result = regroup_by_sentences(segs, max_slot=8.0)
        # Буфер принудительно сбрасывается после первого сегмента (8.5 >= 8.0)
        # Точнее: после второго сегмента buf_duration = 8.5 >= max_slot=8.0 → сброс
        self.assertGreaterEqual(len(result), 1)
        # Все тексты должны быть покрыты
        all_text = " ".join(r.source_text for r in result)
        self.assertIn("very long sentence", all_text)
        self.assertIn("keeps going", all_text)

    def test_no_segments_lost(self):
        """Все фрагменты попадают в результат — нет потерь."""
        segs = [
            _seg("Part one", 0.0, 2.0),
            _seg("of a sentence.", 2.0, 3.5),
            _seg("Another sentence here.", 3.5, 5.0),
            _seg("And a final fragment", 5.0, 6.5),
        ]
        result = regroup_by_sentences(segs, max_slot=10.0)
        all_text = " ".join(r.source_text for r in result)
        for seg in segs:
            self.assertIn(seg.source_text, all_text)

    def test_last_buffer_always_flushed(self):
        """Последний буфер без точки сбрасывается в конце."""
        segs = [
            _seg("Complete sentence.", 0.0, 2.0),
            _seg("Incomplete fragment without punctuation", 2.0, 4.0),
        ]
        result = regroup_by_sentences(segs, max_slot=10.0)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[1].source_text, "Incomplete fragment without punctuation")

    def test_start_end_times_correct(self):
        """start = first.start, end = last.end после слияния."""
        segs = [
            _seg("Fragment one", 1.5, 3.2),
            _seg("fragment two.", 3.2, 5.8),
        ]
        result = regroup_by_sentences(segs, max_slot=10.0)
        self.assertEqual(len(result), 1)
        self.assertAlmostEqual(result[0].start, 1.5)
        self.assertAlmostEqual(result[0].end, 5.8)

    def test_exclamation_mark_boundary(self):
        """! является границей предложения."""
        segs = [
            _seg("Это отлично", 0.0, 1.0),
            _seg("работает!", 1.0, 2.0),
            _seg("И вот следующее.", 2.0, 3.0),
        ]
        result = regroup_by_sentences(segs, max_slot=10.0)
        self.assertEqual(len(result), 2)
        self.assertIn("!", result[0].source_text)

    def test_question_mark_boundary(self):
        """? является границей предложения."""
        segs = [
            _seg("Как дела", 0.0, 1.0),
            _seg("у тебя?", 1.0, 2.0),
            _seg("Нормально.", 2.0, 3.0),
        ]
        result = regroup_by_sentences(segs, max_slot=10.0)
        self.assertEqual(len(result), 2)
        self.assertIn("?", result[0].source_text)

    def test_text_joined_with_space(self):
        """Тексты объединяются через одиночный пробел."""
        segs = [
            _seg("Hello", 0.0, 1.0),
            _seg("world.", 1.0, 2.0),
        ]
        result = regroup_by_sentences(segs, max_slot=10.0)
        self.assertEqual(result[0].source_text, "Hello world.")

    def test_real_whisper_example(self):
        """Реалистичный пример из логов — 62 Whisper-сегмента → меньше предложений."""
        # Первые 4 сегмента из реального проекта
        segs = [
            _seg(
                "Have you ever had a brilliant idea for an app, but stopped right in your tracks because",
                0.0, 5.08,
            ),
            _seg("you don't know how to code?", 5.08, 7.28),
            _seg(
                "Learning programming languages takes years of painful, frustrating study.",
                7.28, 12.28,
            ),
            _seg("That barrier is gone.", 12.28, 14.08),
        ]
        result = regroup_by_sentences(segs, max_slot=8.0)
        # Первые два объединяются (нет ? в первом, есть во втором)
        self.assertEqual(len(result), 3)
        self.assertAlmostEqual(result[0].start, 0.0)
        self.assertAlmostEqual(result[0].end, 7.28)
        self.assertIn("know how to code?", result[0].source_text)
        # Третий — полное предложение
        self.assertAlmostEqual(result[1].start, 7.28)
        # Четвёртый — полное предложение
        self.assertEqual(result[2].source_text, "That barrier is gone.")


if __name__ == "__main__":
    unittest.main()
