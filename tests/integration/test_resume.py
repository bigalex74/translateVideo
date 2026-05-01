"""Интеграционные тесты для возобновления пайплайна."""

import unittest
import tempfile
from pathlib import Path

from translate_video.core.schemas import JobStatus, ProjectStatus
from translate_video.core.store import ProjectStore
from translate_video.pipeline import PipelineRunner, StageContext
from translate_video.cli import _build_stages


class ResumePipelineTest(unittest.TestCase):
    """Проверка логики пропуска и перезапуска этапов."""

    def test_resume_skips_completed_stages(self):
        """Повторный запуск пайплайна пропускает завершенные этапы."""

        with tempfile.TemporaryDirectory() as temp_dir:
            store = ProjectStore(Path(temp_dir) / "runs")
            
            # Первый запуск
            project1 = store.create_project("lesson.mp4", project_id="demo")
            runner1 = PipelineRunner(_build_stages("fake"))
            runs1 = runner1.run(StageContext(project=project1, store=store))
            
            self.assertTrue(all(r.status == JobStatus.COMPLETED for r in runs1))
            
            # Загружаем сохраненный проект и запускаем снова
            project2 = store.load_project(project1.work_dir)
            runner2 = PipelineRunner(_build_stages("fake"))
            runs2 = runner2.run(StageContext(project=project2, store=store))
            
            # Все этапы должны быть пропущены
            self.assertTrue(all(r.status == JobStatus.SKIPPED for r in runs2))

    def test_force_restarts_all_stages(self):
        """Запуск с force перезапускает завершенные этапы."""

        with tempfile.TemporaryDirectory() as temp_dir:
            store = ProjectStore(Path(temp_dir) / "runs")
            
            # Первый запуск
            project1 = store.create_project("lesson.mp4", project_id="demo")
            runner1 = PipelineRunner(_build_stages("fake"))
            runner1.run(StageContext(project=project1, store=store))
            
            # Второй запуск с force
            project2 = store.load_project(project1.work_dir)
            runner2 = PipelineRunner(_build_stages("fake"), force=True)
            runs2 = runner2.run(StageContext(project=project2, store=store))
            
            # Этапы должны выполниться
            self.assertTrue(all(r.status == JobStatus.COMPLETED for r in runs2))


if __name__ == "__main__":
    unittest.main()
