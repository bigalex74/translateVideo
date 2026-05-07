"""Тест консистентности версии (QA агент — предложение iter 2).

Проверяет что VERSION, pyproject.toml и __init__.py содержат
одинаковую версию — защита от рассинхронизации при ручном bump.
"""

import re
from pathlib import Path
import unittest


_ROOT = Path(__file__).parent.parent.parent  # translateVideo/


def _read_pyproject_version(root: Path) -> str:
    text = (root / "pyproject.toml").read_text(encoding="utf-8")
    m = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    assert m, "version не найдена в pyproject.toml"
    return m.group(1)


def _read_file_version(root: Path) -> str:
    return (root / "VERSION").read_text(encoding="utf-8").strip()


def _read_init_version(root: Path) -> str:
    text = (root / "src" / "translate_video" / "__init__.py").read_text(encoding="utf-8")
    m = re.search(r'__version__\s*=\s*"([^"]+)"', text)
    assert m, "__version__ не найдена в __init__.py"
    return m.group(1)


def _read_sw_version(root: Path) -> str:
    text = (root / "ui" / "public" / "sw.js").read_text(encoding="utf-8")
    m = re.search(r"const APP_VERSION = '([^']+)'", text)
    assert m, "APP_VERSION не найдена в ui/public/sw.js"
    return m.group(1)


class TestVersionConsistency(unittest.TestCase):
    """Версия должна быть одинаковой во всех трёх файлах."""

    def test_all_versions_match(self):
        pyproject = _read_pyproject_version(_ROOT)
        file_ver  = _read_file_version(_ROOT)
        init_ver  = _read_init_version(_ROOT)
        sw_ver    = _read_sw_version(_ROOT)

        self.assertEqual(
            pyproject, file_ver,
            f"pyproject.toml ({pyproject}) и VERSION ({file_ver}) расходятся",
        )
        self.assertEqual(
            pyproject, init_ver,
            f"pyproject.toml ({pyproject}) и __init__.py ({init_ver}) расходятся",
        )
        self.assertEqual(
            file_ver, init_ver,
            f"VERSION ({file_ver}) и __init__.py ({init_ver}) расходятся",
        )
        self.assertEqual(
            file_ver, sw_ver,
            f"VERSION ({file_ver}) и ui/public/sw.js ({sw_ver}) расходятся",
        )

    def test_version_format(self):
        """Версия должна быть в формате semver X.Y.Z."""
        ver = _read_file_version(_ROOT)
        self.assertRegex(ver, r"^\d+\.\d+\.\d+$",
                         f"Версия '{ver}' не соответствует semver X.Y.Z")


if __name__ == "__main__":
    unittest.main()
