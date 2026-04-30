import unittest
from pathlib import Path
import tomllib

import translate_video


class VersionMetadataTest(unittest.TestCase):
    def test_version_files_are_aligned(self):
        root = Path(__file__).resolve().parents[2]
        version = (root / "VERSION").read_text(encoding="utf-8").strip()
        pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))

        self.assertEqual(pyproject["project"]["version"], version)
        self.assertEqual(translate_video.__version__, version)


if __name__ == "__main__":
    unittest.main()
