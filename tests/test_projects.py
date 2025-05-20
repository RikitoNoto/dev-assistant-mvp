import time
from datetime import datetime
from fastapi import status
from fastapi.testclient import TestClient
from typing import TYPE_CHECKING, Optional
from unittest.mock import MagicMock


if TYPE_CHECKING:
    from src.api import app
    from src.models.document import PlanDocument, TechSpecDocument
    from src.models.project import Project
    from src.repositories.data.projects import ProjectRepository
    from src.repositories.data.documents import DocumentRepository
else:
    from api import app
    from models.document import PlanDocument, TechSpecDocument
    from models.project import Project
    from repositories.data.projects import ProjectRepository
    from repositories.data.documents import DocumentRepository

from tests.fake_project_repository import FakeProjectRepository
from tests.fake_document_repository import FakeDocumentRepository

# --- Test Class for Project API ---
class TestProjectAPI:
    """Project API (/projects) のテストクラス"""

    def setup_method(self):
        """各テストメソッドの前に実行されるセットアップ"""
        self.fake_project_repo = FakeProjectRepository()
        self.fake_plan_doc_repo = FakeDocumentRepository()
        self.fake_tech_spec_doc_repo = FakeDocumentRepository()
        
        # リポジトリの設定
        Project.set_repository(self.fake_project_repo)
        PlanDocument.set_repository(self.fake_plan_doc_repo)
        TechSpecDocument.set_repository(self.fake_tech_spec_doc_repo)
        
        self.client = TestClient(app)

    def teardown_method(self):
        """各テストメソッドの後に実行されるクリーンアップ"""
        # データをクリア
        self.fake_project_repo.clear()
        self.fake_plan_doc_repo.clear()
        self.fake_tech_spec_doc_repo.clear()
        
        # 新しいテストのために新しいリポジトリインスタンスを設定
        # 次のテストでsetup_methodが呼ばれるので、ここでリポジトリを再設定する必要はない

    # --- Helper Methods ---
    def _create_project_in_repo(self, title: str, create_docs: bool = False, github_project_id: Optional[str] = None) -> Project:
        """テスト用にリポジトリに直接プロジェクトを作成するヘルパー"""
        project = Project(title=title, github_project_id=github_project_id)
        saved_project_id = self.fake_project_repo.save_or_update(project.to_dict())
        saved_project_data = self.fake_project_repo.get_by_id(saved_project_id)
        if not saved_project_data:
            raise Exception("Failed to create project")
            
        # 辞書からProjectオブジェクトを作成
        saved_project = Project.from_dict(saved_project_data)
        
        if create_docs and saved_project:
            project_id_str = str(saved_project_id)
            # 新しいドキュメントモデルを使用
            plan_doc = PlanDocument(project_id=project_id_str, content="Plan for " + title)
            tech_spec_doc = TechSpecDocument(
                project_id=project_id_str, content="Spec for " + title
            )
            # 辞書ベースのアプローチに対応するため、ドキュメントオブジェクトを辞書に変換
            self.fake_plan_doc_repo.save_or_update(plan_doc.to_dict())
            self.fake_tech_spec_doc_repo.save_or_update(tech_spec_doc.to_dict())

        return saved_project

    # --- Test Cases ---

    # POST /projects
    def test_create_project_success(self):
        """POST /projects (成功時) のテスト"""
        project_title = "Test Project Create Success"
        response = self.client.post("/projects", json={"title": project_title})

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["title"] == project_title
        assert "project_id" in data
        assert "created_at" in data
        assert "updated_at" in data

        project_id_from_response = str(data["project_id"])
        saved_project_data = self.fake_project_repo.get_by_id(project_id_from_response)
        assert saved_project_data is not None
        assert saved_project_data["title"] == project_title
        assert saved_project_data["project_id"] == project_id_from_response

    def test_create_project_creates_plan_document(self):
        """POST /projects (計画ドキュメント作成成功時) のテスト"""
        project_title = "Test Project Plan Doc Create"
        response = self.client.post("/projects", json={"title": project_title})

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        project_id_from_response = str(data["project_id"])

        plan_doc_data = self.fake_plan_doc_repo.get_by_id(project_id_from_response)
        assert plan_doc_data is not None
        assert plan_doc_data["project_id"] == project_id_from_response
        assert plan_doc_data["content"] == ""

    def test_create_project_creates_tech_spec_document(self):
        """POST /projects (技術仕様ドキュメント作成成功時) のテスト"""
        project_title = "Test Project Tech Spec Doc Create"
        response = self.client.post("/projects", json={"title": project_title})

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        project_id_from_response = str(data["project_id"])

        tech_spec_doc_data = self.fake_tech_spec_doc_repo.get_by_id(project_id_from_response)
        assert tech_spec_doc_data is not None
        assert tech_spec_doc_data["project_id"] == project_id_from_response
        assert tech_spec_doc_data["content"] == ""

    def test_create_project_failure(self):
        """POST /projects (リポジトリ失敗時) のテスト"""
        mock_project_repo = MagicMock(spec=ProjectRepository)
        mock_project_repo.save_or_update.side_effect = Exception(
            "Database error on project create"
        )
        mock_plan_repo = MagicMock(spec=DocumentRepository)
        mock_tech_spec_repo = MagicMock(spec=DocumentRepository)

        # モックリポジトリを設定
        Project.set_repository(mock_project_repo)
        PlanDocument.set_repository(mock_plan_repo)
        TechSpecDocument.set_repository(mock_tech_spec_repo)

        response = self.client.post("/projects", json={"title": "Fail Project Create"})

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        data = response.json()
        assert "detail" in data
        assert (
            "Failed to create project: Database error on project create"
            in data["detail"]
        )


    def test_create_project_failure_on_doc_save(self):
        """POST /projects (ドキュメント保存失敗時) のテスト"""
        mock_project_repo = FakeProjectRepository()
        mock_plan_repo = MagicMock(spec=DocumentRepository)
        mock_plan_repo.save_or_update.side_effect = Exception(
            "Database error on plan doc create"
        )
        mock_tech_spec_repo = MagicMock(spec=DocumentRepository)

        Project.set_repository(mock_project_repo)
        # PlanDocumentモデルのリポジトリを設定
        PlanDocument.set_repository(mock_plan_repo)
        # TechSpecDocumentモデルのリポジトリを設定
        TechSpecDocument.set_repository(mock_tech_spec_repo)

        response = self.client.post("/projects", json={"title": "Fail Doc Create"})

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        data = response.json()
        assert "detail" in data
        assert (
            "Failed to create project: Database error on plan doc create"
            in data["detail"]
        )

    # GET /projects
    def test_get_all_projects_success(self):
        """GET /projects (成功時、複数プロジェクト) のテスト"""
        proj1 = self._create_project_in_repo("Project Alpha", create_docs=True)
        proj2 = self._create_project_in_repo("Project Beta", create_docs=True)

        response = self.client.get("/projects")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2
        titles_in_response = {p["title"] for p in data}
        ids_in_response = {str(p["project_id"]) for p in data}
        assert proj1.title in titles_in_response
        assert proj2.title in titles_in_response
        assert str(proj1.project_id) in ids_in_response
        assert str(proj2.project_id) in ids_in_response

    def test_get_all_projects_empty(self):
        """GET /projects (成功時、プロジェクトなし) のテスト"""
        response = self.client.get("/projects")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    def test_get_all_projects_failure(self):
        """GET /projects (リポジトリ失敗時) のテスト"""
        mock_project_repo = MagicMock(spec=ProjectRepository)
        mock_project_repo.get_all.side_effect = Exception("Database error on get all")
        Project.set_repository(mock_project_repo)

        response = self.client.get("/projects")

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        data = response.json()
        assert "detail" in data
        assert "Failed to get projects: Database error on get all" in data["detail"]


    # GET /projects/{project_id}
    def test_get_project_by_id_success(self):
        """GET /projects/{project_id} (成功時) のテスト"""
        proj = self._create_project_in_repo("Project Gamma", create_docs=True)

        response = self.client.get(f"/projects/{proj.project_id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["project_id"] == str(proj.project_id)
        assert data["title"] == proj.title
        assert datetime.fromisoformat(data["created_at"]) == proj.created_at
        assert datetime.fromisoformat(data["updated_at"]) == proj.updated_at

    def test_get_project_by_id_not_found(self):
        """GET /projects/{project_id} (存在しないID) のテスト"""
        non_existent_id = "non_existent_id"
        response = self.client.get(f"/projects/{non_existent_id}")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert "detail" in data
        assert f"Project with ID '{non_existent_id}' not found" in data["detail"]

    def test_get_project_by_id_failure(self):
        """GET /projects/{project_id} (リポジトリ失敗時) のテスト"""
        proj_id = "non_existent_id"
        mock_project_repo = MagicMock(spec=ProjectRepository)
        mock_project_repo.get_by_id.side_effect = Exception(
            "Database error on get by id"
        )
        Project.set_repository(mock_project_repo)

        response = self.client.get(f"/projects/{proj_id}")

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        data = response.json()
        assert "detail" in data
        assert "Failed to get project: Database error on get by id" in data["detail"]

    # PUT /projects/{project_id}
    def test_update_project_success(self):
        """PUT /projects/{project_id} (成功時) のテスト"""
        proj = self._create_project_in_repo("Initial Title", create_docs=True)
        updated_title = "Updated Project Title"
        original_updated_at = proj.updated_at

        time.sleep(0.01)

        response = self.client.put(
            f"/projects/{proj.project_id}",
            json={"title": updated_title},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["project_id"] == str(proj.project_id)
        assert data["title"] == updated_title
        new_updated_at = datetime.fromisoformat(data["updated_at"])
        assert new_updated_at > original_updated_at
        assert datetime.fromisoformat(data["created_at"]) == proj.created_at

        saved_project_data = self.fake_project_repo.get_by_id(proj.project_id)
        assert saved_project_data is not None
        assert saved_project_data["title"] == updated_title
        # 日付が辞書の場合とオブジェクトの場合を処理
        if isinstance(saved_project_data["updated_at"], str):
            saved_updated_at = datetime.fromisoformat(saved_project_data["updated_at"])
        else:
            saved_updated_at = saved_project_data["updated_at"]
        # 新しい更新日時が古い更新日時より後であることを確認
        assert saved_updated_at > original_updated_at

        plan_doc_data = self.fake_plan_doc_repo.get_by_id(proj.project_id)
        assert plan_doc_data is not None
        assert plan_doc_data["content"] == "Plan for Initial Title"

        tech_spec_doc_data = self.fake_tech_spec_doc_repo.get_by_id(proj.project_id)
        assert tech_spec_doc_data is not None
        assert tech_spec_doc_data["content"] == "Spec for Initial Title"

    def test_update_project_not_found(self):
        """PUT /projects/{project_id} (存在しないID) のテスト"""
        non_existent_id = "non_existent_id"
        response = self.client.put(
            f"/projects/{non_existent_id}", json={"title": "Update Fail"}
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert "detail" in data
        assert f"Project with ID '{non_existent_id}' not found" in data["detail"]

    def test_update_project_failure(self):
        """PUT /projects/{project_id} (リポジトリ失敗時) のテスト"""
        proj = self._create_project_in_repo("Project To Fail Update", create_docs=True)
        mock_project_repo = MagicMock(spec=ProjectRepository)
        # 辞書を返すように設定
        mock_project_repo.get_by_id.return_value = proj.to_dict()
        mock_project_repo.save_or_update.side_effect = Exception(
            "Database error on update"
        )
        Project.set_repository(mock_project_repo)

        response = self.client.put(
            f"/projects/{proj.project_id}",
            json={"title": "Updated Project Title"},
        )

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        data = response.json()
        assert "detail" in data
        assert "Failed to update project: Database error on update" in data["detail"]

    # DELETE /projects/{project_id}
    def test_delete_project_success(self):
        """DELETE /projects/{project_id} (成功時) のテスト"""
        proj = self._create_project_in_repo("Project To Delete", create_docs=True)
        project_id = proj.project_id

        response = self.client.delete(f"/projects/{proj.project_id}")

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not response.content

        deleted_project = self.fake_project_repo.get_by_id(project_id)
        assert deleted_project is None

        plan_doc = self.fake_plan_doc_repo.get_by_id(project_id)
        assert plan_doc is not None

        tech_spec_doc = self.fake_tech_spec_doc_repo.get_by_id(project_id)
        assert tech_spec_doc is not None

    def test_delete_project_not_found(self):
        """DELETE /projects/{project_id} (存在しないID) のテスト"""
        non_existent_id = "non_existent_id"

        response = self.client.delete(f"/projects/{non_existent_id}")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert "detail" in data
        assert f"Project with ID '{non_existent_id}' not found" in data["detail"]

    def test_delete_project_failure(self):
        """DELETE /projects/{project_id} (リポジトリ失敗時) のテスト"""
        proj = self._create_project_in_repo("Project To Fail Delete", create_docs=True)
        mock_project_repo = MagicMock(spec=ProjectRepository)
        # 辞書を返すように設定
        mock_project_repo.get_by_id.return_value = proj.to_dict()
        mock_project_repo.delete_by_id.side_effect = Exception(
            "Database error on delete"
        )
        Project.set_repository(mock_project_repo)

        response = self.client.delete(f"/projects/{proj.project_id}")

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        data = response.json()
        assert "detail" in data
        assert "Failed to delete project: Database error on delete" in data["detail"]
        
    # POST /projects/{project_id}/open
    def test_update_project_last_opened_at_success(self):
        """POST /projects/{project_id}/open (成功時) のテスト"""
        proj = self._create_project_in_repo("Project To Open", create_docs=True)
        original_last_opened_at = proj.last_opened_at
        
        # 時間差を確実に作るために少し待機
        time.sleep(0.01)
        
        response = self.client.post(f"/projects/{proj.project_id}/open", json={})
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["project_id"] == str(proj.project_id)
        assert data["title"] == proj.title
        
        # last_opened_at が更新されていることを確認
        new_last_opened_at = datetime.fromisoformat(data["last_opened_at"])
        assert new_last_opened_at > original_last_opened_at
        
        # リポジトリ内のプロジェクトも更新されていることを確認
        updated_project_data = self.fake_project_repo.get_by_id(proj.project_id)
        assert updated_project_data is not None
        # 日付が辞書の場合とオブジェクトの場合を処理
        if isinstance(updated_project_data["last_opened_at"], str):
            saved_last_opened_at = datetime.fromisoformat(updated_project_data["last_opened_at"])
        else:
            saved_last_opened_at = updated_project_data["last_opened_at"]
        assert saved_last_opened_at > original_last_opened_at
        
    def test_update_project_last_opened_at_not_found(self):
        """POST /projects/{project_id}/open (存在しないID) のテスト"""
        non_existent_id = "non_existent_id"
        
        response = self.client.post(f"/projects/{non_existent_id}/open", json={})
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert "detail" in data
        assert f"Project with ID '{non_existent_id}' not found" in data["detail"]
        
    def test_update_project_last_opened_at_failure(self):
        """POST /projects/{project_id}/open (リポジトリ失敗時) のテスト"""
        proj = self._create_project_in_repo("Project To Fail Open", create_docs=True)
        mock_project_repo = MagicMock(spec=ProjectRepository)
        # 辞書を返すように設定
        mock_project_repo.get_by_id.return_value = proj.to_dict()
        mock_project_repo.save_or_update.side_effect = Exception(
            "Database error on update last_opened_at"
        )
        Project.set_repository(mock_project_repo)
        
        response = self.client.post(f"/projects/{proj.project_id}/open", json={})
        
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        data = response.json()
        assert "detail" in data
        assert "Failed to update project last_opened_at" in data["detail"]
    
    # POST /projects/{project_id}/github
    def test_register_github_project_success(self):
        """POST /projects/{project_id}/github (成功時) のテスト"""
        # プロジェクトを作成
        proj = self._create_project_in_repo("Test GitHub Project Registration", create_docs=True)
        github_project_id = "gp_12345"
        
        # APIエンドポイントを呼び出し
        response = self.client.post(
            f"/projects/{proj.project_id}/github",
            json={"github_project_id": github_project_id}
        )
        
        # レスポンスを検証
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["project_id"] == str(proj.project_id)
        assert data["title"] == proj.title
        assert data["github_project_id"] == github_project_id
        
        # リポジトリに保存されたデータを検証
        saved_project_data = self.fake_project_repo.get_by_id(proj.project_id)
        assert saved_project_data is not None
        assert saved_project_data["github_project_id"] == github_project_id
    
    def test_register_github_project_not_found(self):
        """POST /projects/{project_id}/github (存在しないID) のテスト"""
        non_existent_id = "non_existent_id"
        github_project_id = "gp_12345"
        
        response = self.client.post(
            f"/projects/{non_existent_id}/github",
            json={"github_project_id": github_project_id}
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert "detail" in data
        assert f"Project with ID '{non_existent_id}' not found" in data["detail"]
    
    def test_register_github_project_failure(self):
        """POST /projects/{project_id}/github (リポジトリ失敗時) のテスト"""
        # プロジェクトを作成
        proj = self._create_project_in_repo("Project To Fail GitHub Registration", create_docs=True)
        github_project_id = "gp_12345"
        
        # モックリポジトリを設定
        mock_project_repo = MagicMock(spec=ProjectRepository)
        mock_project_repo.get_by_id.return_value = proj.to_dict()
        mock_project_repo.save_or_update.side_effect = Exception(
            "Database error on update github_project_id"
        )
        Project.set_repository(mock_project_repo)
        
        response = self.client.post(
            f"/projects/{proj.project_id}/github",
            json={"github_project_id": github_project_id}
        )
        
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        data = response.json()
        assert "detail" in data
        assert "Failed to register GitHub project: Database error on update github_project_id" in data["detail"]
