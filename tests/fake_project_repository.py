from src.models.project import Project
from src.repositories.projects import ProjectRepository
from typing import Optional

class FakeProjectRepository(ProjectRepository):
    """インメモリでプロジェクトを管理するFakeリポジトリクラス"""

    def __init__(self):
        self._projects: dict[str, Project] = {}


    def save_or_update(self, project: Project) -> str:
        """プロジェクトを保存または更新する"""

        project_id = project.project_id

        if project_id in self._projects:
            updated_project = Project(
                **project.model_dump(),
            )
            self._projects[project_id] = updated_project
            return project_id
        else:
            new_project = Project(
                **project.model_dump(),
            )
            self._projects[project_id] = new_project
            return project_id

    def get_by_id(self, project_id: str) -> Optional[Project]:
        """IDでプロジェクトを取得する"""
        return self._projects.get(project_id)

    def get_all(self) -> list[Project]:
        """すべてのプロジェクトを取得する"""
        return list(self._projects.values())

    def delete_by_id(self, project_id: str) -> bool:
        """IDでプロジェクトを削除する"""
        if project_id in self._projects:
            del self._projects[project_id]
            return True
        raise ValueError(f"Project with ID '{project_id}' not found.")

    def clear(self):
        """テスト用にリポジトリをクリアする"""
        self._projects = {}
