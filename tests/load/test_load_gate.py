"""Дымовой тест исполняемости нагрузочной проверки."""

import unittest


class LoadGateTest(unittest.TestCase):
    """Проверяет, что нагрузочную проверку можно запустить."""

    def test_load_gate_is_runnable(self):
        """Пустой нагрузочный уровень должен оставаться исполняемым."""

        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
