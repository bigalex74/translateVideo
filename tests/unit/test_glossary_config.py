"""Unit-тесты glossary_terms в PipelineConfig (Z2.9).

Проверяет сохранение, валидацию и сериализацию поля glossary_terms.
"""

import unittest

from translate_video.core.config import PipelineConfig


class GlossaryTermsConfigTest(unittest.TestCase):
    """Тесты поля glossary_terms в PipelineConfig."""

    def test_glossary_terms_default_empty(self):
        """По умолчанию glossary_terms — пустой список."""
        cfg = PipelineConfig()
        self.assertEqual(cfg.glossary_terms, [])

    def test_glossary_terms_can_be_set(self):
        """glossary_terms можно задать при создании."""
        terms = [{"source": "AI", "target": "ИИ"}, {"source": "CPU", "target": "ЦПУ"}]
        cfg = PipelineConfig(glossary_terms=terms)
        self.assertEqual(len(cfg.glossary_terms), 2)
        self.assertEqual(cfg.glossary_terms[0]["source"], "AI")

    def test_glossary_terms_serialized(self):
        """glossary_terms включается в to_dict()."""
        terms = [{"source": "GPU", "target": "видеокарта"}]
        cfg = PipelineConfig(glossary_terms=terms)
        d = cfg.to_dict()
        self.assertIn("glossary_terms", d)
        self.assertEqual(d["glossary_terms"][0]["source"], "GPU")

    def test_glossary_terms_deserialized(self):
        """glossary_terms восстанавливается из from_dict()."""
        d = {"glossary_terms": [{"source": "LLM", "target": "ЯМ"}]}
        cfg = PipelineConfig.from_dict(d)
        self.assertEqual(len(cfg.glossary_terms), 1)
        self.assertEqual(cfg.glossary_terms[0]["target"], "ЯМ")

    def test_glossary_terms_missing_uses_default(self):
        """Отсутствие поля в JSON → пустой список."""
        cfg = PipelineConfig.from_dict({})
        self.assertEqual(cfg.glossary_terms, [])

    def test_glossary_terms_roundtrip(self):
        """Полный цикл сериализации сохраняет данные."""
        terms = [
            {"source": "API", "target": "АПИ"},
            {"source": "backend", "target": "бэкенд"},
        ]
        cfg = PipelineConfig(glossary_terms=terms)
        restored = PipelineConfig.from_dict(cfg.to_dict())
        self.assertEqual(restored.glossary_terms, terms)

    def test_glossary_terms_empty_roundtrip(self):
        """Пустой glossary_terms сохраняется как пустой список."""
        cfg = PipelineConfig(glossary_terms=[])
        restored = PipelineConfig.from_dict(cfg.to_dict())
        self.assertEqual(restored.glossary_terms, [])


if __name__ == "__main__":
    unittest.main()
