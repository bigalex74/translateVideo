"""Release metadata and gate checks for Sprint 1."""

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


class ReleaseMetadataTest(unittest.TestCase):
    """Checks that release metadata cannot silently drift."""

    def test_public_roadmap_current_version_matches_version_file(self):
        version = _read("VERSION").strip()
        roadmap = _read("PUBLIC_ROADMAP.md")
        match = re.search(r"\*\*Текущая версия:\*\*\s*([0-9]+\.[0-9]+\.[0-9]+)", roadmap)

        self.assertIsNotNone(match, "PUBLIC_ROADMAP.md must contain '**Текущая версия:** X.Y.Z'")
        self.assertEqual(match.group(1), version)

    def test_latest_changelog_entry_matches_version_file(self):
        version = _read("VERSION").strip()
        changelog = _read("change.log")
        match = re.search(r"^##\s+([0-9]+\.[0-9]+\.[0-9]+)\b", changelog, re.MULTILINE)

        self.assertIsNotNone(match, "change.log must start with a SemVer release entry")
        self.assertEqual(match.group(1), version)

    def test_version_is_semver(self):
        version = _read("VERSION").strip()
        self.assertRegex(version, SEMVER_RE)

    def test_release_checklist_exists(self):
        checklist = ROOT / "docs" / "release-checklist.md"
        self.assertTrue(checklist.exists(), "docs/release-checklist.md is required")
        text = checklist.read_text(encoding="utf-8")
        self.assertIn("make ci:quick", text)
        self.assertIn("make test:release", text)
        self.assertIn("/api/health", text)

    def test_ci_workflow_exists_and_runs_quick_gate(self):
        workflow = ROOT / ".github" / "workflows" / "release-gate.yml"
        self.assertTrue(workflow.exists(), ".github/workflows/release-gate.yml is required")
        text = workflow.read_text(encoding="utf-8")
        self.assertIn("make ci:quick", text)
        self.assertIn("docker build", text)

    def test_docker_and_compose_have_healthchecks(self):
        dockerfile = _read("Dockerfile")
        compose = _read("docker-compose.yml")
        self.assertIn("HEALTHCHECK", dockerfile)
        self.assertIn("healthcheck:", compose)


if __name__ == "__main__":
    unittest.main()
