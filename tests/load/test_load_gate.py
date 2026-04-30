"""Дымовой тест исполняемости нагрузочной проверки."""

import unittest
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from translate_video.core.store import ProjectStore
from translate_video.pipeline import PipelineRunner, StageContext
from translate_video.cli import _build_stages
from translate_video.core.schemas import JobStatus


class LoadGateTest(unittest.TestCase):
    """Проверяет стабильность хранилища и пайплайна под нагрузкой."""

    def test_concurrent_project_creation(self):
        """Создание 20 проектов параллельно должно работать без конфликтов."""

        with tempfile.TemporaryDirectory() as temp_dir:
            store = ProjectStore(Path(temp_dir) / "runs")
            
            def create_proj(i):
                return store.create_project("input.mp4", project_id=f"proj_{i}")
                
            with ThreadPoolExecutor(max_workers=5) as executor:
                projects = list(executor.map(create_proj, range(20)))
                
            self.assertEqual(len(projects), 20)
            
            # Проверяем, что все проекты создались и независимы
            for i in range(20):
                proj = store.load_project(projects[i].work_dir)
                self.assertEqual(proj.id, f"proj_{i}")

    def test_pipeline_isolation(self):
        """Последовательный запуск fake-пайплайна на 10 проектах не должен смешивать артефакты."""

        with tempfile.TemporaryDirectory() as temp_dir:
            store = ProjectStore(Path(temp_dir) / "runs")
            projects = [store.create_project("input.mp4", project_id=f"iso_{i}") for i in range(10)]
            
            runner = PipelineRunner(_build_stages("fake"))
            
            for project in projects:
                context = StageContext(project=project, store=store)
                runs = runner.run(context)
                self.assertTrue(all(r.status == JobStatus.COMPLETED for r in runs))
                
            for project in projects:
                restored = store.load_project(project.work_dir)
                # Проверяем, что артефакты каждого проекта лежат в его папке
                for record in restored.artifact_records:
                    # Относительный путь должен быть в папке текущего проекта
                    full_path = restored.work_dir / record.path
                    self.assertTrue(full_path.exists())


if __name__ == "__main__":
    unittest.main()
