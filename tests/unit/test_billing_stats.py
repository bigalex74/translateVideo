"""TVIDEO-082: тесты billing в compute_project_stats.

Биллинг теперь основан на снапшотах баланса (billing_snapshots),
а не на приблизительных оценках токенов.
"""
import unittest
from pathlib import Path

from translate_video.core.config import PipelineConfig
from translate_video.core.schemas import (
    Segment,
    SegmentStatus,
    VideoProject,
)
from translate_video.core.stats import compute_project_stats


def _make_project(
    provider: str = "polza",
    snapshots: dict | None = None,
) -> VideoProject:
    cfg = PipelineConfig()
    project = VideoProject(
        id="billing_test",
        input_video=Path("test.mp4"),
        work_dir=Path("/tmp/billing_test"),
        config=cfg,
    )

    _src = "This is a longer source sentence used for billing test. " * 3
    _tgt = "Это тестовое предложение для проверки биллинга. " * 3

    def _seg(i: int) -> Segment:
        s = Segment(id=f"s{i}", start=float(i), end=float(i + 2), source_text=_src)
        s.translated_text = _tgt
        s.qa_flags = [
            "translation_llm",
            "translation_provider_used",
            f"translation_provider_{provider}",
        ]
        s.tts_path = None
        s.tts_text = _tgt
        s.confidence = 0.9
        s.status = SegmentStatus.TRANSLATED
        return s

    project.segments = [_seg(0), _seg(1), _seg(2)]
    project.stage_runs = []
    project.status = "completed"
    project.billing_snapshots = snapshots or {}
    return project


class BillingStatsTest(unittest.TestCase):
    """TVIDEO-082: billing секция в compute_project_stats."""

    # ── Структура ─────────────────────────────────────────────────────────────

    def test_billing_key_present(self):
        """compute_project_stats всегда возвращает ключ billing."""
        result = compute_project_stats(_make_project())
        self.assertIn("billing", result)
        self.assertIsNotNone(result["billing"])

    def test_billing_has_required_keys(self):
        """Billing содержит все обязательные ключи."""
        billing = compute_project_stats(_make_project())["billing"]
        required = {
            "dominant_translation_provider",
            "polza_before", "polza_after", "polza_spent_rub",
            "neuroapi_before", "neuroapi_after", "neuroapi_spent_usd",
            "has_real_data", "note",
        }
        for k in required:
            self.assertIn(k, billing, f"Missing key: {k}")

    # ── Без снапшотов ─────────────────────────────────────────────────────────

    def test_no_snapshots_returns_none_fields(self):
        """Без снапшотов все spent-поля = None и has_real_data = False."""
        billing = compute_project_stats(_make_project(snapshots={}))["billing"]
        self.assertIsNone(billing["polza_spent_rub"])
        self.assertIsNone(billing["neuroapi_spent_usd"])
        self.assertFalse(billing["has_real_data"])

    def test_no_snapshots_note_mentions_rerun(self):
        """Без снапшотов note подсказывает перезапустить перевод."""
        billing = compute_project_stats(_make_project(snapshots={}))["billing"]
        self.assertIn("запустите", billing["note"])

    # ── Polza снапшоты ────────────────────────────────────────────────────────

    def test_polza_spent_computed_correctly(self):
        """polza_spent_rub = polza_before - polza_after."""
        snaps = {"polza_before": 1000.0, "polza_after": 983.45}
        billing = compute_project_stats(_make_project(snapshots=snaps))["billing"]
        self.assertAlmostEqual(billing["polza_spent_rub"], 16.55, places=2)

    def test_polza_zero_spent(self):
        """polza_spent_rub = 0 если баланс не изменился."""
        snaps = {"polza_before": 500.0, "polza_after": 500.0}
        billing = compute_project_stats(_make_project(snapshots=snaps))["billing"]
        self.assertEqual(billing["polza_spent_rub"], 0.0)

    def test_polza_has_real_data_true(self):
        """has_real_data = True если есть Polza снапшоты."""
        snaps = {"polza_before": 1000.0, "polza_after": 995.0}
        billing = compute_project_stats(_make_project(snapshots=snaps))["billing"]
        self.assertTrue(billing["has_real_data"])

    # ── NeuroAPI снапшоты ─────────────────────────────────────────────────────

    def test_neuroapi_spent_computed_correctly(self):
        """neuroapi_spent_usd = neuroapi_before - neuroapi_after."""
        snaps = {"neuroapi_before": 10.0, "neuroapi_after": 9.8712}
        billing = compute_project_stats(_make_project(snapshots=snaps))["billing"]
        self.assertAlmostEqual(billing["neuroapi_spent_usd"], 0.1288, places=4)

    def test_neuroapi_has_real_data_true(self):
        """has_real_data = True если есть NeuroAPI снапшоты."""
        snaps = {"neuroapi_before": 5.0, "neuroapi_after": 4.95}
        billing = compute_project_stats(_make_project(snapshots=snaps))["billing"]
        self.assertTrue(billing["has_real_data"])

    # ── Partial снапшоты ──────────────────────────────────────────────────────

    def test_partial_snapshot_only_before(self):
        """Только before без after → spent = None для этого провайдера."""
        snaps = {"polza_before": 1000.0}  # нет polza_after
        billing = compute_project_stats(_make_project(snapshots=snaps))["billing"]
        self.assertIsNone(billing["polza_spent_rub"])

    def test_mixed_providers_partial(self):
        """Polza есть, NeuroAPI нет → has_real_data = True (хоть один провайдер)."""
        snaps = {"polza_before": 1000.0, "polza_after": 990.0}
        billing = compute_project_stats(_make_project(snapshots=snaps))["billing"]
        self.assertTrue(billing["has_real_data"])
        self.assertIsNone(billing["neuroapi_spent_usd"])

    # ── Провайдер ─────────────────────────────────────────────────────────────

    def test_dominant_provider_polza(self):
        """dominant_translation_provider = polza при QA-флаге polza."""
        billing = compute_project_stats(_make_project("polza"))["billing"]
        self.assertEqual(billing["dominant_translation_provider"], "polza")

    def test_dominant_provider_neuroapi(self):
        """dominant_translation_provider = neuroapi при QA-флаге neuroapi."""
        billing = compute_project_stats(_make_project("neuroapi"))["billing"]
        self.assertEqual(billing["dominant_translation_provider"], "neuroapi")


if __name__ == "__main__":
    unittest.main()
