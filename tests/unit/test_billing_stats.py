"""TVIDEO-082: тесты _compute_billing в compute_project_stats.

Проверяет:
- billing присутствует в результате compute_project_stats
- estimated_cost_usd > 0 при LLM-провайдере с ненулевой ценой
- bесплатные провайдеры (google, gemini) → cost = 0.0
- Токены вычисляются корректно из chars
- rewrite_cost > 0 если задан professional_rewrite_provider
"""
import unittest
from translate_video.core.config import PipelineConfig
from translate_video.core.schemas import Segment, SegmentStatus, VideoProject
from translate_video.core.stats import compute_project_stats
from pathlib import Path


def _make_project(
    provider: str = "polza",
    rewrite_provider: str | None = None,
) -> VideoProject:
    cfg = PipelineConfig()
    cfg.professional_rewrite_provider = rewrite_provider or ""
    project = VideoProject(
        id="billing_test",
        input_video=Path("test.mp4"),
        work_dir=Path("/tmp/billing_test"),
        config=cfg,
    )

    # Длинные сегменты (>300 chars каждый) чтобы billing > 0.0001 и не округлялся в 0
    _src = "This is a longer source sentence used for billing calculation testing. " * 3
    _tgt = "Это более длинное предложение для расчёта биллинга в тестах. " * 3

    def _seg(i: int, provider_flag: str) -> Segment:
        s = Segment(id=f"s{i}", start=float(i), end=float(i + 2), source_text=_src)
        s.translated_text = _tgt
        s.qa_flags = ["translation_llm", "translation_provider_used", f"translation_provider_{provider_flag}"]
        s.tts_path = None
        s.tts_text = _tgt
        s.confidence = 0.9
        s.status = SegmentStatus.TRANSLATED
        return s

    project.segments = [_seg(0, provider), _seg(1, provider), _seg(2, provider)]
    project.stage_runs = []
    project.status = "completed"
    return project


class BillingStatsTest(unittest.TestCase):
    """TVIDEO-082: billing секция в compute_project_stats."""

    def test_billing_key_present(self):
        """compute_project_stats всегда возвращает ключ billing."""
        project = _make_project("polza")
        result = compute_project_stats(project)
        self.assertIn("billing", result)
        self.assertIsNotNone(result["billing"])

    def test_paid_provider_has_nonzero_cost(self):
        """При LLM-провайдере polza стоимость > 0."""
        project = _make_project("polza")
        billing = compute_project_stats(project)["billing"]
        self.assertGreater(billing["estimated_cost_usd"], 0)
        self.assertGreater(billing["estimated_cost_translate_usd"], 0)

    def test_google_provider_has_zero_cost(self):
        """Google (бесплатный) → cost = 0.0."""
        project = _make_project("google")
        billing = compute_project_stats(project)["billing"]
        self.assertEqual(billing["estimated_cost_translate_usd"], 0.0)

    def test_gemini_provider_has_zero_cost(self):
        """Gemini free-tier → cost = 0.0."""
        project = _make_project("gemini")
        billing = compute_project_stats(project)["billing"]
        self.assertEqual(billing["estimated_cost_translate_usd"], 0.0)

    def test_tokens_computed_from_chars(self):
        """Токены вычислены как chars / 3.5 (≈ round down)."""
        project = _make_project("polza")
        result = compute_project_stats(project)
        source_chars = result["segments"]["source_chars"]
        billing = result["billing"]
        expected_input = int(source_chars / 3.5)
        self.assertEqual(billing["estimated_input_tokens"], expected_input)

    def test_rewrite_cost_zero_when_no_provider(self):
        """rewrite_cost = 0 если нет professional rewrite провайдера."""
        project = _make_project("polza", rewrite_provider=None)
        billing = compute_project_stats(project)["billing"]
        self.assertEqual(billing["estimated_cost_rewrite_usd"], 0.0)

    def test_rewrite_cost_nonzero_when_provider_set(self):
        """rewrite_cost > 0 при professional_rewrite_provider = neuroapi."""
        project = _make_project("polza", rewrite_provider="neuroapi")
        billing = compute_project_stats(project)["billing"]
        self.assertGreater(billing["estimated_cost_rewrite_usd"], 0.0)

    def test_total_cost_equals_translate_plus_rewrite(self):
        """estimated_cost_usd = translate + rewrite (округление)."""
        project = _make_project("polza", rewrite_provider="neuroapi")
        billing = compute_project_stats(project)["billing"]
        expected = round(
            billing["estimated_cost_translate_usd"] + billing["estimated_cost_rewrite_usd"],
            4,
        )
        self.assertAlmostEqual(billing["estimated_cost_usd"], expected, places=4)

    def test_dominant_provider_correct(self):
        """dominant_translation_provider = polza когда все сегменты через polza."""
        project = _make_project("polza")
        billing = compute_project_stats(project)["billing"]
        self.assertEqual(billing["dominant_translation_provider"], "polza")

    def test_note_present(self):
        """note поле всегда присутствует в billing."""
        billing = compute_project_stats(_make_project())["billing"]
        self.assertIn("note", billing)
        self.assertIsInstance(billing["note"], str)


if __name__ == "__main__":
    unittest.main()
