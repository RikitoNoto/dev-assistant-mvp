from typing import Optional, Dict, Any, List

from src.repositories.projects import ProjectRepository

class FakeProjectRepository(ProjectRepository):
    """インメモリでプロジェクトを管理するFakeリポジトリクラス"""

    def __init__(self):
        self._projects: Dict[str, Dict[str, Any]] = {}


    def save_or_update(self, project_data: Dict[str, Any]) -> str:
        """プロジェクトを保存または更新する"""

        project_id = project_data["project_id"]

        # 辞書のコピーを作成して保存
        self._projects[project_id] = project_data.copy()
        return project_id

    def get_by_id(self, project_id: str) -> Optional[Dict[str, Any]]:
        """IDでプロジェクトを取得する"""
        return self._projects.get(project_id)

    def get_all(self) -> List[Dict[str, Any]]:
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
