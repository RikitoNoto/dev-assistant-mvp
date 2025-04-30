# tests/test_projects.py
import uuid
import time  # time.sleep を使うためにインポート
from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import UUID

from fastapi import status
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

# テスト対象のFastAPIアプリケーションとモデル、リポジトリ等をインポート
from api import app  # FastAPIアプリケーションインスタンス
from models import Project
from repositories.projects import (
    ProjectRepository,
)  # Fakeが継承するため、またはモックのspec用
from routers.utils import get_project_repository  # 依存性注入用


# --- Fake Project Repository Class ---
class FakeProjectRepository(ProjectRepository):
    """インメモリでプロジェクトを管理するFakeリポジトリクラス"""

    def __init__(self):
        self._projects: Dict[UUID, Project] = {}

    def save_or_update(self, project: Project) -> UUID:
        """プロジェクトを保存または更新する"""
        if not isinstance(project, Project):
            raise TypeError("project must be an instance of Project")

        project_id = getattr(project, "project_id", None)
        now = datetime.now(timezone.utc)

        if project_id and project_id in self._projects:
            # Update
            existing_project = self._projects[project_id]
            # Create a new instance with updated fields
            updated_project = Project(
                project_id=existing_project.project_id,
                title=project.title,  # Use title from the input project
                created_at=existing_project.created_at,  # Keep original created_at
                updated_at=now,  # Set new updated_at
            )
            self._projects[project_id] = updated_project
            return project_id
        else:
            # Create
            new_id = project_id or uuid.uuid4()
            # Create a new instance
            new_project = Project(
                project_id=new_id,
                title=project.title,
                created_at=getattr(project, "created_at", now),  # Use provided or new
                updated_at=now,
            )
            self._projects[new_id] = new_project
            return new_id

    def get_by_id(self, project_id: UUID) -> Optional[Project]:
        """IDでプロジェクトを取得する"""
        return self._projects.get(project_id)

    def get_all(self) -> List[Project]:
        """すべてのプロジェクトを取得する"""
        return list(self._projects.values())

    def delete_by_id(self, project_id: UUID) -> bool:
        """IDでプロジェクトを削除する"""
        if project_id in self._projects:
            del self._projects[project_id]
            return True
        # 存在しない場合はリポジトリ層でエラーを出す想定
        # (ルーター側でハンドリングされる)
        # ここではテスト用にシンプルにFalseを返すか、あるいはValueErrorを発生させる
        # ルーターの実装に合わせてValueErrorを発生させる方がより正確
        raise ValueError(f"Project with ID '{project_id}' not found.")

    def clear(self):
        """テスト用にリポジトリをクリアする"""
        self._projects = {}


# --- Test Class for Project API ---
class TestProjectAPI:
    """Project API (/projects) のテストクラス"""

    def setup_method(self):
        """各テストメソッドの前に実行されるセットアップ"""
        self.client = TestClient(app)
        self.fake_repo = FakeProjectRepository()
        # このクラスのテストで使用する依存関係をオーバーライド
        app.dependency_overrides[get_project_repository] = lambda: self.fake_repo

    def teardown_method(self):
        """各テストメソッドの後に実行されるクリーンアップ"""
        # オーバーライドを解除
        if get_project_repository in app.dependency_overrides:
            del app.dependency_overrides[get_project_repository]
        self.fake_repo.clear()  # 各テスト後にリポジトリをクリア

    # --- Helper Methods ---
    def _create_project_in_repo(self, title: str) -> Project:
        """テスト用にリポジトリに直接プロジェクトを作成するヘルパー"""
        project = Project(title=title)
        # save_or_updateがproject_idを返すように変更
        saved_project_id = self.fake_repo.save_or_update(project)
        # 保存されたオブジェクトを返す（IDやタイムスタンプが含まれる）
        return self.fake_repo.get_by_id(saved_project_id)

    # --- Test Cases ---

    # POST /projects
    def test_create_project_success(self):
        """POST /projects (成功時) のテスト"""
        project_title = "Test Project Create Success"
        response = self.client.post("/projects", json={"title": project_title})

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["title"] == project_title
        assert "project_id" in data  # id -> project_id
        assert "created_at" in data
        assert "updated_at" in data

        # Fakeリポジトリの状態を確認
        project_id_from_response = UUID(data["project_id"])  # id -> project_id
        saved_project = self.fake_repo.get_by_id(project_id_from_response)
        assert saved_project is not None
        assert saved_project.title == project_title
        assert saved_project.project_id == project_id_from_response  # id -> project_id

    def test_create_project_failure(self):
        """POST /projects (リポジトリ失敗時) のテスト"""
        mock_repo = MagicMock(spec=ProjectRepository)
        mock_repo.save_or_update.side_effect = Exception("Database error on create")
        app.dependency_overrides[get_project_repository] = lambda: mock_repo

        response = self.client.post("/projects", json={"title": "Fail Project"})

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        data = response.json()
        assert "detail" in data
        assert "Failed to create project: Database error on create" in data["detail"]

        # このテストで使用したオーバーライドを解除
        del app.dependency_overrides[get_project_repository]

    # GET /projects
    def test_get_all_projects_success(self):
        """GET /projects (成功時、複数プロジェクト) のテスト"""
        # 事前にデータを準備
        proj1 = self._create_project_in_repo("Project Alpha")
        proj2 = self._create_project_in_repo("Project Beta")

        response = self.client.get("/projects")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2
        # レスポンスの内容を確認 (順序は不定の場合があるためIDで検索)
        titles_in_response = {p["title"] for p in data}
        ids_in_response = {UUID(p["project_id"]) for p in data}  # id -> project_id
        assert proj1.title in titles_in_response
        assert proj2.title in titles_in_response
        assert proj1.project_id in ids_in_response  # id -> project_id
        assert proj2.project_id in ids_in_response  # id -> project_id

    def test_get_all_projects_empty(self):
        """GET /projects (成功時、プロジェクトなし) のテスト"""
        response = self.client.get("/projects")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    def test_get_all_projects_failure(self):
        """GET /projects (リポジトリ失敗時) のテスト"""
        mock_repo = MagicMock(spec=ProjectRepository)
        mock_repo.get_all.side_effect = Exception("Database error on get all")
        app.dependency_overrides[get_project_repository] = lambda: mock_repo

        response = self.client.get("/projects")

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        data = response.json()
        assert "detail" in data
        assert "Failed to get projects: Database error on get all" in data["detail"]

        del app.dependency_overrides[get_project_repository]

    # GET /projects/{project_id}
    def test_get_project_by_id_success(self):
        """GET /projects/{project_id} (成功時) のテスト"""
        proj = self._create_project_in_repo("Project Gamma")

        response = self.client.get(f"/projects/{proj.project_id}")  # id -> project_id

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["project_id"] == str(proj.project_id)  # id -> project_id
        assert data["title"] == proj.title
        # タイムスタンプの比較 (ISO形式文字列)
        assert datetime.fromisoformat(data["created_at"]) == proj.created_at
        assert datetime.fromisoformat(data["updated_at"]) == proj.updated_at

    def test_get_project_by_id_not_found(self):
        """GET /projects/{project_id} (存在しないID) のテスト"""
        non_existent_id = uuid.uuid4()
        response = self.client.get(f"/projects/{non_existent_id}")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert "detail" in data
        assert f"Project with ID '{non_existent_id}' not found" in data["detail"]

    def test_get_project_by_id_failure(self):
        """GET /projects/{project_id} (リポジトリ失敗時) のテスト"""
        proj_id = uuid.uuid4()  # ダミーID
        mock_repo = MagicMock(spec=ProjectRepository)
        mock_repo.get_by_id.side_effect = Exception("Database error on get by id")
        app.dependency_overrides[get_project_repository] = lambda: mock_repo

        response = self.client.get(f"/projects/{proj_id}")

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        data = response.json()
        assert "detail" in data
        assert "Failed to get project: Database error on get by id" in data["detail"]

        del app.dependency_overrides[get_project_repository]

    # PUT /projects/{project_id}
    def test_update_project_success(self):
        """PUT /projects/{project_id} (成功時) のテスト"""
        proj = self._create_project_in_repo("Initial Title")
        updated_title = "Updated Project Title"

        # タイムスタンプが確実に変わるように少し待機 (時間を少し増やす)
        time.sleep(0.01)

        response = self.client.put(
            f"/projects/{proj.project_id}",
            json={"title": updated_title},  # id -> project_id
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["project_id"] == str(proj.project_id)  # id -> project_id
        assert data["title"] == updated_title
        # updated_atが更新されていることを確認 (created_atは不変)
        original_updated_at = proj.updated_at
        new_updated_at = datetime.fromisoformat(data["updated_at"])
        assert new_updated_at > original_updated_at
        assert datetime.fromisoformat(data["created_at"]) == proj.created_at

        # Fakeリポジトリの状態を確認
        saved_project = self.fake_repo.get_by_id(proj.project_id)  # id -> project_id
        assert saved_project is not None
        assert saved_project.title == updated_title
        assert saved_project.updated_at == new_updated_at

    def test_update_project_not_found(self):
        """PUT /projects/{project_id} (存在しないID) のテスト"""
        non_existent_id = uuid.uuid4()
        response = self.client.put(
            f"/projects/{non_existent_id}", json={"title": "Update Fail"}
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert "detail" in data
        assert f"Project with ID '{non_existent_id}' not found" in data["detail"]

    def test_update_project_failure(self):
        """PUT /projects/{project_id} (リポジトリ失敗時) のテスト"""
        proj = self._create_project_in_repo("Project To Fail Update")
        mock_repo = MagicMock(spec=ProjectRepository)
        # get_by_idは成功させるが、save_or_updateで失敗させる
        mock_repo.get_by_id.return_value = proj  # 既存プロジェクトを返すように設定
        mock_repo.save_or_update.side_effect = Exception("Database error on update")
        app.dependency_overrides[get_project_repository] = lambda: mock_repo

        response = self.client.put(
            f"/projects/{proj.project_id}",
            json={"title": "Update Fail"},  # id -> project_id
        )

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        data = response.json()
        assert "detail" in data
        assert "Failed to update project: Database error on update" in data["detail"]

        del app.dependency_overrides[get_project_repository]

    # DELETE /projects/{project_id}
    def test_delete_project_success(self):
        """DELETE /projects/{project_id} (成功時) のテスト"""
        proj = self._create_project_in_repo("Project To Delete")

        response = self.client.delete(
            f"/projects/{proj.project_id}"
        )  # id -> project_id

        assert response.status_code == status.HTTP_204_NO_CONTENT
        # レスポンスボディは空のはず
        assert not response.content

        # Fakeリポジトリの状態を確認
        deleted_project = self.fake_repo.get_by_id(proj.project_id)  # id -> project_id
        assert deleted_project is None

    def test_delete_project_not_found(self):
        """DELETE /projects/{project_id} (存在しないID) のテスト"""
        non_existent_id = uuid.uuid4()

        # Fakeリポジトリのdelete_by_idがValueErrorを発生させることを利用
        response = self.client.delete(f"/projects/{non_existent_id}")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert "detail" in data
        # Fakeリポジトリが発生させるエラーメッセージを確認
        assert f"Project with ID '{non_existent_id}' not found" in data["detail"]

    def test_delete_project_failure(self):
        """DELETE /projects/{project_id} (リポジトリ失敗時) のテスト"""
        proj = self._create_project_in_repo("Project To Fail Delete")
        mock_repo = MagicMock(spec=ProjectRepository)
        mock_repo.delete_by_id.side_effect = Exception("Database error on delete")
        app.dependency_overrides[get_project_repository] = lambda: mock_repo

        response = self.client.delete(
            f"/projects/{proj.project_id}"
        )  # id -> project_id

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        data = response.json()
        assert "detail" in data
        assert "Failed to delete project: Database error on delete" in data["detail"]

        del app.dependency_overrides[get_project_repository]
