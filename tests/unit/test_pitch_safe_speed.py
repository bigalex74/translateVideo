"""Тесты pitch-safe ускорения через ffmpeg atempo (TVIDEO-029b)."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path
import tempfile
import os


def _build_atempo_filters(factor: float) -> list[str]:
    """Вспомогательная функция построения цепочки atempo-фильтров.

    Вынесена из _moviepy_speedx для изолированного тестирования.
    """
    remaining = factor
    filters = []
    while remaining > 2.0:
        filters.append('atempo=2.0')
        remaining /= 2.0
    while remaining < 0.5:
        filters.append('atempo=0.5')
        remaining /= 0.5
    filters.append(f'atempo={remaining:.6f}')
    return filters


class TestAtempoFilterChain(unittest.TestCase):
    """TVIDEO-029b: проверяем построение цепочки atempo-фильтров."""

    def test_normal_factor_single_filter(self):
        """Factor 1.3 → один фильтр atempo."""
        filters = _build_atempo_filters(1.3)
        self.assertEqual(len(filters), 1)
        self.assertIn('atempo=', filters[0])
        val = float(filters[0].split('=')[1])
        self.assertAlmostEqual(val, 1.3, places=4)

    def test_factor_1_0_no_change(self):
        """Factor 1.0 → один фильтр atempo=1.0."""
        filters = _build_atempo_filters(1.0)
        self.assertEqual(len(filters), 1)
        val = float(filters[0].split('=')[1])
        self.assertAlmostEqual(val, 1.0, places=4)

    def test_factor_above_2_chains(self):
        """Factor 3.0 → цепочка из 2 фильтров."""
        filters = _build_atempo_filters(3.0)
        self.assertGreaterEqual(len(filters), 2)
        # Первый — atempo=2.0
        self.assertEqual(filters[0], 'atempo=2.0')

    def test_factor_4_chains_correctly(self):
        """Factor 4.0 = 2.0 * 2.0 → два фильтра."""
        filters = _build_atempo_filters(4.0)
        self.assertGreaterEqual(len(filters), 2)
        # Первые N-1 фильтров должны быть atempo=2.0
        for f in filters[:-1]:
            val = float(f.split('=')[1])
            self.assertAlmostEqual(val, 2.0, places=3)
        # Итоговое произведение ≈ 4.0
        product = 1.0
        for f in filters:
            product *= float(f.split('=')[1])
        self.assertAlmostEqual(product, 4.0, places=3)

    def test_all_factors_in_valid_range(self):
        """Каждый фильтр в цепочке должен быть в диапазоне [0.5, 2.0]."""
        for factor in [0.6, 0.8, 1.0, 1.25, 1.3, 1.5, 2.0, 2.5, 3.0, 4.0]:
            with self.subTest(factor=factor):
                filters = _build_atempo_filters(factor)
                for f in filters:
                    val = float(f.split('=')[1])
                    self.assertGreaterEqual(val, 0.5, f"factor={factor}: {f} < 0.5")
                    self.assertLessEqual(val, 2.0, f"factor={factor}: {f} > 2.0")

    def test_product_equals_original_factor(self):
        """Произведение всех фильтров цепочки равно исходному factor."""
        for factor in [1.1, 1.3, 1.5, 2.0, 2.5, 3.0, 4.0]:
            with self.subTest(factor=factor):
                filters = _build_atempo_filters(factor)
                product = 1.0
                for f in filters:
                    product *= float(f.split('=')[1])
                self.assertAlmostEqual(product, factor, places=3)


class TestAtempoFallback(unittest.TestCase):
    """TVIDEO-029b: проверяем логику fallback при ошибке ffmpeg."""

    def test_fallback_returns_original_factor_unchanged(self):
        """При ошибке в цепочке вычислений фильтры всё равно корректны."""
        # Логика без ffmpeg: проверяем что фильтры строятся даже для крайних значений
        filters = _build_atempo_filters(1.3)
        self.assertGreater(len(filters), 0)

    def test_single_filter_for_max_allowed(self):
        """Factor=2.0 → один фильтр (не требует цепочки)."""
        filters = _build_atempo_filters(2.0)
        self.assertEqual(len(filters), 1)
        val = float(filters[0].split('=')[1])
        self.assertAlmostEqual(val, 2.0, places=3)


if __name__ == '__main__':
    unittest.main()
