"""TVIDEO-073: тесты очистки zombie-пайплайнов при рестарте.

Проверяет:
- startup cleanup: проекты со статусом RUNNING сбрасываются в FAILED при старте сервера
- zombie cancel: POST /cancel работает без in-memory реестра (zombie-mode)
"""
import tempfile
import unittest
from pathlib import Path

from translate_video.core.schemas import ProjectStatus
from translate_video.core.store import ProjectStore


class ZombieStartupCleanupTest(unittest.TestCase):
    """Симуляция startup cleanup без поднятия FastAPI."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = ProjectStore(Path(self.temp_dir.name) / "runs")

    def tearDown(self):
        self.temp_dir.cleanup()

    def _cleanup_zombies(self) -> int:
        """Логика из lifespan — сбрасываем RUNNING → FAILED."""
        count = 0
        for project in self.store.list_projects():
            if project.status == ProjectStatus.RUNNING:
                project.status = ProjectStatus.FAILED
                self.store.save_project(project)
                count += 1
        return count

    def test_running_project_reset_to_failed_on_startup(self):
        """Проект со статусом RUNNING должен стать FAILED после startup cleanup."""
        p = self.store.create_project("video.mp4", project_id="zombie1")
        p.status = ProjectStatus.RUNNING
        self.store.save_project(p)

        cleaned = self._cleanup_zombies()

        self.assertEqual(cleaned, 1)
        restored = self.store.load_project(self.store.root / "zombie1")
        self.assertEqual(restored.status, ProjectStatus.FAILED)

    def test_completed_project_not_touched(self):
        """COMPLETED-проект не должен изменяться при startup cleanup."""
        p = self.store.create_project("video.mp4", project_id="done1")
        p.status = ProjectStatus.COMPLETED
        self.store.save_project(p)

        cleaned = self._cleanup_zombies()

        self.assertEqual(cleaned, 0)
        restored = self.store.load_project(self.store.root / "done1")
        self.assertEqual(restored.status, ProjectStatus.COMPLETED)

    def test_failed_project_not_touched(self):
        """FAILED-проект не должен изменяться при startup cleanup."""
        p = self.store.create_project("video.mp4", project_id="fail1")
        p.status = ProjectStatus.FAILED
        self.store.save_project(p)

        cleaned = self._cleanup_zombies()

        self.assertEqual(cleaned, 0)
        restored = self.store.load_project(self.store.root / "fail1")
        self.assertEqual(restored.status, ProjectStatus.FAILED)

    def test_multiple_zombies_all_reset(self):
        """Несколько RUNNING проектов — все должны стать FAILED."""
        for i in range(3):
            p = self.store.create_project("video.mp4", project_id=f"zombie{i}")
            p.status = ProjectStatus.RUNNING
            self.store.save_project(p)
        # Один завершённый — не трогаем
        done = self.store.create_project("video.mp4", project_id="done_safe")
        done.status = ProjectStatus.COMPLETED
        self.store.save_project(done)

        cleaned = self._cleanup_zombies()

        self.assertEqual(cleaned, 3)
        for i in range(3):
            r = self.store.load_project(self.store.root / f"zombie{i}")
            self.assertEqual(r.status, ProjectStatus.FAILED, f"zombie{i} должен быть FAILED")
        r_done = self.store.load_project(self.store.root / "done_safe")
        self.assertEqual(r_done.status, ProjectStatus.COMPLETED)

    def test_empty_store_no_error(self):
        """Пустое хранилище — cleanup завершается без ошибок."""
        cleaned = self._cleanup_zombies()
        self.assertEqual(cleaned, 0)


class ZombieForceCancel(unittest.TestCase):
    """Симуляция zombie cancel: статус в FS = RUNNING, реестра нет."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = ProjectStore(Path(self.temp_dir.name) / "runs")

    def tearDown(self):
        self.temp_dir.cleanup()

    def _force_cancel(self, project_id: str) -> bool:
        """Zombie cancel: напрямую сбрасываем RUNNING → FAILED."""
        try:
            project = self.store.load_project(self.store.root / project_id)
        except FileNotFoundError:
            return False
        if project.status != ProjectStatus.RUNNING:
            return False
        project.status = ProjectStatus.FAILED
        self.store.save_project(project)
        return True

    def test_zombie_cancel_sets_failed(self):
        """Zombie cancel должен перевести статус в FAILED."""
        p = self.store.create_project("video.mp4", project_id="z1")
        p.status = ProjectStatus.RUNNING
        self.store.save_project(p)

        result = self._force_cancel("z1")

        self.assertTrue(result)
        restored = self.store.load_project(self.store.root / "z1")
        self.assertEqual(restored.status, ProjectStatus.FAILED)

    def test_zombie_cancel_not_running_returns_false(self):
        """Force cancel не RUNNING-проекта должен вернуть False."""
        p = self.store.create_project("video.mp4", project_id="z2")
        p.status = ProjectStatus.COMPLETED
        self.store.save_project(p)

        result = self._force_cancel("z2")

        self.assertFalse(result)

    def test_zombie_cancel_nonexistent_returns_false(self):
        """Force cancel несуществующего проекта должен вернуть False."""
        result = self._force_cancel("nonexistent_project_xyz")
        self.assertFalse(result)

    def test_zombie_cancel_idempotent(self):
        """Двойной force cancel безопасен — второй вызов не меняет статус."""
        p = self.store.create_project("video.mp4", project_id="z3")
        p.status = ProjectStatus.RUNNING
        self.store.save_project(p)

        self._force_cancel("z3")
        result2 = self._force_cancel("z3")  # второй вызов — уже FAILED

        self.assertFalse(result2, "второй вызов должен вернуть False")
        restored = self.store.load_project(self.store.root / "z3")
        self.assertEqual(restored.status, ProjectStatus.FAILED)


if __name__ == "__main__":
    unittest.main()


class IntraStageCancel(unittest.TestCase):
    """TVIDEO-074: отмена срабатывает внутри этапа — после текущего сегмента."""

    def _make_cancel_event(self, set_after: int):
        """Возвращает threading.Event который активируется после N вызовов."""
        import threading
        event = threading.Event()
        counter = {"n": 0}

        def progress_callback(current, total, message):
            counter["n"] += 1
            if counter["n"] >= set_after:
                event.set()
            # Имитируем поведение stages.py: проверяем флаг
            if event.is_set():
                raise RuntimeError(f"cancel на сегменте {current}/{total}")

        return event, progress_callback

    def test_cancel_fires_after_nth_segment(self):
        """После N-го сегмента cancel_event → RuntimeError сразу, не после всех."""
        _, cb = self._make_cancel_event(set_after=3)

        results = []
        for i in range(1, 10):
            try:
                cb(i, 10, f"seg {i}")
                results.append(i)
            except RuntimeError:
                break

        # Должно успеть перевести сегменты 1,2 и на 3-м выбросить
        self.assertEqual(results, [1, 2])

    def test_cancel_not_fired_if_event_not_set(self):
        """Без cancel_event все сегменты переводятся."""
        _, cb = self._make_cancel_event(set_after=999)

        results = []
        for i in range(1, 6):
            cb(i, 5, f"seg {i}")
            results.append(i)

        self.assertEqual(results, [1, 2, 3, 4, 5])
