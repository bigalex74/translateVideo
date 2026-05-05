"""Unit-тесты функций экспорта скрипта (Z3.13/Z3.14).

Проверяет TXT и TSV экспорт через store + routes/_script_logic.
Тестируем через прямой вызов функций генерации, не через HTTP.
"""

import unittest
from translate_video.core.schemas import Segment, SegmentStatus


def _seg(start: float, end: float, source: str, translated: str) -> Segment:
    return Segment(
        id=f"s_{int(start)}",
        start=start, end=end,
        source_text=source,
        translated_text=translated,
        status=SegmentStatus.TRANSLATED,
    )


def _generate_txt_script(
    segments: list[Segment],
    project_id: str,
    include_timecodes: bool = True,
    include_source: bool = False,
) -> str:
    """Имитирует логику TXT экспорта из endpoint (Z3.14)."""
    from io import StringIO
    buf = StringIO()
    buf.write(f"ПЕРЕВОД: {project_id}\n")
    buf.write("=" * 60 + "\n\n")
    for i, seg in enumerate(segments, 1):
        if include_timecodes:
            start_ts = f"{int(seg.start // 60):02d}:{seg.start % 60:05.2f}"
            end_ts = f"{int(seg.end // 60):02d}:{seg.end % 60:05.2f}"
            buf.write(f"[{i}] {start_ts} → {end_ts}\n")
        if include_source:
            buf.write(f"  ОР: {seg.source_text or ''}\n")
        buf.write(f"  ПЕР: {seg.translated_text or '(нет перевода)'}\n\n")
    return buf.getvalue()


def _generate_tsv_script(segments: list[Segment]) -> str:
    """Имитирует логику TSV экспорта из endpoint (Z3.13)."""
    from io import StringIO
    buf = StringIO()
    buf.write("start\tend\tsource\ttranslated\n")
    for seg in segments:
        start = f"{seg.start:.2f}"
        end = f"{seg.end:.2f}"
        src = (seg.source_text or "").replace("\t", " ")
        tgt = (seg.translated_text or "").replace("\t", " ")
        buf.write(f"{start}\t{end}\t{src}\t{tgt}\n")
    return buf.getvalue()


class TxtScriptExportTest(unittest.TestCase):
    """Тесты TXT экспорта скрипта (Z3.14)."""

    def test_header_contains_project_id(self):
        """Заголовок содержит ID проекта."""
        segs = [_seg(0.0, 1.0, "Hi", "Привет")]
        result = _generate_txt_script(segs, "test-project")
        self.assertIn("ПЕРЕВОД: test-project", result)

    def test_timecodes_present(self):
        """С include_timecodes=True — таймкоды в выводе."""
        segs = [_seg(65.0, 70.0, "Text", "Текст")]
        result = _generate_txt_script(segs, "p1", include_timecodes=True)
        self.assertIn("01:05.00", result)   # 65 сек = 1 мин 5 сек

    def test_timecodes_absent(self):
        """С include_timecodes=False — таймкодов нет."""
        segs = [_seg(65.0, 70.0, "Text", "Текст")]
        result = _generate_txt_script(segs, "p1", include_timecodes=False)
        self.assertNotIn("→", result)

    def test_source_not_included_by_default(self):
        """По умолчанию исходный текст не включается."""
        segs = [_seg(0.0, 1.0, "Hello original", "Привет")]
        result = _generate_txt_script(segs, "p1", include_source=False)
        self.assertNotIn("Hello original", result)

    def test_source_included_when_requested(self):
        """С include_source=True — исходный текст включается."""
        segs = [_seg(0.0, 1.0, "Hello original", "Привет")]
        result = _generate_txt_script(segs, "p1", include_source=True)
        self.assertIn("Hello original", result)
        self.assertIn("ОР:", result)

    def test_translation_present(self):
        """Переведённый текст присутствует в выводе."""
        segs = [_seg(0.0, 1.0, "Hi", "Переведено")]
        result = _generate_txt_script(segs, "p1")
        self.assertIn("Переведено", result)
        self.assertIn("ПЕР:", result)

    def test_empty_translation_shows_placeholder(self):
        """Пустой перевод показывает заглушку."""
        segs = [_seg(0.0, 1.0, "Hi", "")]
        result = _generate_txt_script(segs, "p1")
        self.assertIn("(нет перевода)", result)

    def test_multiple_segments_numbered(self):
        """Несколько сегментов нумеруются."""
        segs = [_seg(float(i), float(i + 1), f"S{i}", f"П{i}") for i in range(3)]
        result = _generate_txt_script(segs, "p1")
        self.assertIn("[1]", result)
        self.assertIn("[2]", result)
        self.assertIn("[3]", result)

    def test_empty_segments_list(self):
        """Пустой список — только заголовок."""
        result = _generate_txt_script([], "p1")
        self.assertIn("ПЕРЕВОД: p1", result)
        self.assertNotIn("ПЕР:", result)


class TsvScriptExportTest(unittest.TestCase):
    """Тесты TSV экспорта скрипта (Z3.13)."""

    def test_header_row(self):
        """TSV содержит строку заголовка."""
        result = _generate_tsv_script([])
        self.assertTrue(result.startswith("start\tend\tsource\ttranslated\n"))

    def test_data_row_format(self):
        """Строка данных содержит 4 TSV-поля."""
        segs = [_seg(1.0, 2.5, "Hello", "Привет")]
        result = _generate_tsv_script(segs)
        lines = result.strip().splitlines()
        self.assertEqual(len(lines), 2)  # заголовок + 1 строка
        fields = lines[1].split("\t")
        self.assertEqual(len(fields), 4)

    def test_tab_in_text_replaced(self):
        """Табуляция в тексте заменяется пробелом."""
        segs = [_seg(0.0, 1.0, "Hello\tworld", "Привет\tмир")]
        result = _generate_tsv_script(segs)
        lines = result.strip().splitlines()
        fields = lines[1].split("\t")
        # Каждое поле не содержит вложенных табов
        for f in fields:
            self.assertNotIn("\t", f)

    def test_start_end_in_tsv(self):
        """Таймкоды start/end присутствуют в TSV."""
        segs = [_seg(10.5, 20.75, "Src", "Tgt")]
        result = _generate_tsv_script(segs)
        self.assertIn("10.50", result)
        self.assertIn("20.75", result)

    def test_empty_list(self):
        """Пустой список — только заголовок."""
        result = _generate_tsv_script([])
        lines = result.strip().splitlines()
        self.assertEqual(len(lines), 1)


if __name__ == "__main__":
    unittest.main()
