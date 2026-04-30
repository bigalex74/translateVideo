"""Дымовой тест исполняемости E2E-проверки."""

import unittest


class E2EGateTest(unittest.TestCase):
    """Проверяет, что E2E-проверку можно запустить."""

    def test_e2e_gate_is_runnable(self):
        """Пустой E2E-уровень должен оставаться исполняемым."""

        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
