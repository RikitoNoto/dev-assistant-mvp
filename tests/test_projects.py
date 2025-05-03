import time
from datetime import datetime, timezone
from typing import Dict, List, Optional
import random
import string

from fastapi import status
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

from api import app
from models import Project, Document
from repositories.projects import ProjectRepository
from repositories.documents import DocumentRepository
from routers.utils import (
    get_project_repository,
    get_plan_document_repository,
    get_tech_spec_document_repository,
)


# --- Fake Project Repository Class ---
class FakeProjectRepository(ProjectRepository):
    """インメモリでプロジェクトを管理するFakeリポジトリクラス"""

    def __init__(self):
        self._projects: Dict[str, Project] = {}

    def _generate_id(self) -> str:
        """テスト用のランダムな文字列IDを生成する"""
        return "".join(random.choices(string.ascii_lowercase + string.digits, k=12))

    def save_or_update(self, project: Project) -> str:
        """プロジェクトを保存または更新する"""
        if not isinstance(project, Project):
            raise TypeError("project must be an instance of Project")

        project_id = getattr(project, "project_id", None)
        now = datetime.now(timezone.utc)

        if project_id and project_id in self._projects:
            existing_project = self._projects[project_id]
            updated_project = Project(
                project_id=existing_project.project_id,
                title=project.title,
                created_at=existing_project.created_at,
                updated_at=now,
            )
            self._projects[project_id] = updated_project
            return str(project_id)
        else:
            new_id = project_id or self._generate_id()
            new_project = Project(
                project_id=str(new_id),
                title=project.title,
                created_at=getattr(project, "created_at", now),
                updated_at=now,
            )
            self._projects[str(new_id)] = new_project
            return str(new_id)

    def get_by_id(self, project_id: str) -> Optional[Project]:
        """IDでプロジェクトを取得する"""
        return self._projects.get(str(project_id))

    def get_all(self) -> List[Project]:
        """すべてのプロジェクトを取得する"""
        return list(self._projects.values())

    def delete_by_id(self, project_id: str) -> bool:
        """IDでプロジェクトを削除する"""
        project_id_str = str(project_id)
        if project_id_str in self._projects:
            del self._projects[project_id_str]
            return True
        raise ValueError(f"Project with ID '{project_id_str}' not found.")

    def clear(self):
        """テスト用にリポジトリをクリアする"""
        self._projects = {}


# --- Fake Document Repository Class ---
class FakeDocumentRepository(DocumentRepository):
    """インメモリでドキュメントを管理するFakeリポジトリクラス"""

    def __init__(self):
        self._documents: Dict[str, Document] = {}
        self._documents_by_doc_id: Dict[str, Document] = {}

    def _generate_id(self) -> str:
        """テスト用のランダムな文字列IDを生成する"""
        return "".join(random.choices(string.ascii_lowercase + string.digits, k=12))

    def initialize(self, *args, **kwargs):
        return super().initialize(*args, **kwargs)

    def save_or_update(self, document: Document) -> str:
        """ドキュメントを保存または更新する"""
        if not isinstance(document, Document):
            raise TypeError("document must be an instance of Document")

        doc_id = getattr(document, "document_id", None)  # str or None
        project_id = getattr(document, "project_id", None)  # str or None
        now = datetime.now(timezone.utc)

        if not project_id:
            raise ValueError("project_id is required to save a document")

        project_id_str = str(project_id)
        doc_id_str = str(doc_id) if doc_id else None

        if doc_id_str and doc_id_str in self._documents_by_doc_id:
            existing_doc = self._documents_by_doc_id[doc_id_str]
            updated_doc = Document(
                document_id=existing_doc.document_id,
                project_id=existing_doc.project_id,
                content=document.content,
                created_at=existing_doc.created_at,
                updated_at=now,
            )
            self._documents_by_doc_id[doc_id_str] = updated_doc
            self._documents[project_id_str] = updated_doc
            return doc_id_str
        else:
            new_doc_id = doc_id_str or self._generate_id()
            new_document = Document(
                document_id=str(new_doc_id),
                project_id=project_id_str,
                content=document.content,
                created_at=getattr(document, "created_at", now),
                updated_at=now,
            )
            self._documents[project_id_str] = new_document
            self._documents_by_doc_id[str(new_doc_id)] = new_document
            return str(new_doc_id)

    def get_by_id(self, document_id: str) -> Optional[Document]:
        """ドキュメントIDでドキュメントを取得する"""
        return self._documents_by_doc_id.get(str(document_id))

    def get_by_project_id(self, project_id: str) -> Optional[Document]:
        """プロジェクトIDでドキュメントを取得する（単純化：最初に見つかったものを返す）"""
        return self._documents.get(str(project_id))

    def get_all_by_project_id(self, project_id: str) -> List[Document]:
        """指定されたプロジェクトIDのすべてのドキュメントを取得する"""
        docs = []
        project_id_str = str(project_id)
        for doc in self._documents_by_doc_id.values():
            if doc.project_id == project_id_str:
                docs.append(doc)
        return docs

    def delete_by_id(self, document_id: str) -> bool:
        """ドキュメントIDでドキュメントを削除する"""
        doc_id_str = str(document_id)
        if doc_id_str in self._documents_by_doc_id:
            doc_to_delete = self._documents_by_doc_id.pop(doc_id_str)
            # _documents 辞書からも削除
            if doc_to_delete.project_id in self._documents:
                # 削除対象のドキュメントIDと一致するか確認
                if self._documents[doc_to_delete.project_id].document_id == doc_id_str:
                    del self._documents[doc_to_delete.project_id]
            return True
        return False

    def clear(self):
        """テスト用にリポジトリをクリアする"""
        self._documents = {}
        self._documents_by_doc_id = {}


# --- Test Class for Project API ---
class TestProjectAPI:
    """Project API (/projects) のテストクラス"""

    def setup_method(self):
        """各テストメソッドの前に実行されるセットアップ"""
        self.client = TestClient(app)
        self.fake_project_repo = FakeProjectRepository()
        self.fake_plan_doc_repo = FakeDocumentRepository()
        self.fake_tech_spec_doc_repo = FakeDocumentRepository()
        app.dependency_overrides[get_project_repository] = (
            lambda: self.fake_project_repo
        )
        app.dependency_overrides[get_plan_document_repository] = (
            lambda: self.fake_plan_doc_repo
        )
        app.dependency_overrides[get_tech_spec_document_repository] = (
            lambda: self.fake_tech_spec_doc_repo
        )

    def teardown_method(self):
        """各テストメソッドの後に実行されるクリーンアップ"""
        if get_project_repository in app.dependency_overrides:
            del app.dependency_overrides[get_project_repository]
        if get_plan_document_repository in app.dependency_overrides:
            del app.dependency_overrides[get_plan_document_repository]
        if get_tech_spec_document_repository in app.dependency_overrides:
            del app.dependency_overrides[get_tech_spec_document_repository]

        self.fake_project_repo.clear()
        self.fake_plan_doc_repo.clear()
        self.fake_tech_spec_doc_repo.clear()

    # --- Helper Methods ---
    def _create_project_in_repo(self, title: str, create_docs: bool = False) -> Project:
        """テスト用にリポジトリに直接プロジェクトを作成するヘルパー"""
        project = Project(title=title)
        saved_project_id = self.fake_project_repo.save_or_update(project)
        saved_project = self.fake_project_repo.get_by_id(saved_project_id)

        if create_docs and saved_project:
            project_id_str = str(saved_project_id)
            plan_doc = Document(project_id=project_id_str, content="Plan for " + title)
            tech_spec_doc = Document(
                project_id=project_id_str, content="Spec for " + title
            )
            self.fake_plan_doc_repo.save_or_update(plan_doc)
            self.fake_tech_spec_doc_repo.save_or_update(tech_spec_doc)

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
        saved_project = self.fake_project_repo.get_by_id(project_id_from_response)
        assert saved_project is not None
        assert saved_project.title == project_title
        assert saved_project.project_id == project_id_from_response

    def test_create_project_creates_plan_document(self):
        """POST /projects (計画ドキュメント作成成功時) のテスト"""
        project_title = "Test Project Plan Doc Create"
        response = self.client.post("/projects", json={"title": project_title})

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        project_id_from_response = str(data["project_id"])

        plan_doc = self.fake_plan_doc_repo.get_by_project_id(project_id_from_response)
        assert plan_doc is not None
        assert plan_doc.project_id == str(project_id_from_response)
        assert plan_doc.content == ""

    def test_create_project_creates_tech_spec_document(self):
        """POST /projects (技術仕様ドキュメント作成成功時) のテスト"""
        project_title = "Test Project Tech Spec Doc Create"
        response = self.client.post("/projects", json={"title": project_title})

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        project_id_from_response = str(data["project_id"])

        tech_spec_doc = self.fake_tech_spec_doc_repo.get_by_project_id(
            project_id_from_response
        )
        assert tech_spec_doc is not None
        assert tech_spec_doc.project_id == str(project_id_from_response)
        assert tech_spec_doc.content == ""

    def test_create_project_failure(self):
        """POST /projects (リポジトリ失敗時) のテスト"""
        mock_project_repo = MagicMock(spec=ProjectRepository)
        mock_project_repo.save_or_update.side_effect = Exception(
            "Database error on project create"
        )
        mock_plan_repo = MagicMock(spec=DocumentRepository)
        mock_tech_spec_repo = MagicMock(spec=DocumentRepository)

        app.dependency_overrides[get_project_repository] = lambda: mock_project_repo
        app.dependency_overrides[get_plan_document_repository] = lambda: mock_plan_repo
        app.dependency_overrides[get_tech_spec_document_repository] = (
            lambda: mock_tech_spec_repo
        )

        response = self.client.post("/projects", json={"title": "Fail Project Create"})

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        data = response.json()
        assert "detail" in data
        assert (
            "Failed to create project: Database error on project create"
            in data["detail"]
        )

        del app.dependency_overrides[get_project_repository]
        del app.dependency_overrides[get_plan_document_repository]
        del app.dependency_overrides[get_tech_spec_document_repository]

    def test_create_project_failure_on_doc_save(self):
        """POST /projects (ドキュメント保存失敗時) のテスト"""
        mock_project_repo = FakeProjectRepository()
        mock_plan_repo = MagicMock(spec=DocumentRepository)
        mock_plan_repo.save_or_update.side_effect = Exception(
            "Database error on plan doc create"
        )
        mock_tech_spec_repo = MagicMock(spec=DocumentRepository)

        app.dependency_overrides[get_project_repository] = lambda: mock_project_repo
        app.dependency_overrides[get_plan_document_repository] = lambda: mock_plan_repo
        app.dependency_overrides[get_tech_spec_document_repository] = (
            lambda: mock_tech_spec_repo
        )

        response = self.client.post("/projects", json={"title": "Fail Doc Create"})

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        data = response.json()
        assert "detail" in data
        assert (
            "Failed to create project: Database error on plan doc create"
            in data["detail"]
        )

        del app.dependency_overrides[get_project_repository]
        del app.dependency_overrides[get_plan_document_repository]
        del app.dependency_overrides[get_tech_spec_document_repository]

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
        app.dependency_overrides[get_project_repository] = lambda: mock_project_repo

        response = self.client.get("/projects")

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        data = response.json()
        assert "detail" in data
        assert "Failed to get projects: Database error on get all" in data["detail"]

        del app.dependency_overrides[get_project_repository]

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
        non_existent_id = self.fake_project_repo._generate_id()
        response = self.client.get(f"/projects/{non_existent_id}")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert "detail" in data
        assert f"Project with ID '{non_existent_id}' not found" in data["detail"]

    def test_get_project_by_id_failure(self):
        """GET /projects/{project_id} (リポジトリ失敗時) のテスト"""
        proj_id = self.fake_project_repo._generate_id()
        mock_project_repo = MagicMock(spec=ProjectRepository)
        mock_project_repo.get_by_id.side_effect = Exception(
            "Database error on get by id"
        )
        app.dependency_overrides[get_project_repository] = lambda: mock_project_repo

        response = self.client.get(f"/projects/{proj_id}")

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        data = response.json()
        assert "detail" in data
        assert "Failed to get project: Database error on get by id" in data["detail"]

        del app.dependency_overrides[get_project_repository]

    # PUT /projects/{project_id}
    def test_update_project_success(self):
        """PUT /projects/{project_id} (成功時) のテスト"""
        proj = self._create_project_in_repo("Initial Title", create_docs=True)
        updated_title = "Updated Project Title"

        time.sleep(0.01)

        response = self.client.put(
            f"/projects/{proj.project_id}",
            json={"title": updated_title},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["project_id"] == str(proj.project_id)
        assert data["title"] == updated_title
        original_updated_at = proj.updated_at
        new_updated_at = datetime.fromisoformat(data["updated_at"])
        assert new_updated_at > original_updated_at
        assert datetime.fromisoformat(data["created_at"]) == proj.created_at

        saved_project = self.fake_project_repo.get_by_id(proj.project_id)
        assert saved_project is not None
        assert saved_project.title == updated_title
        assert saved_project.updated_at == new_updated_at

        plan_doc = self.fake_plan_doc_repo.get_by_project_id(proj.project_id)
        assert plan_doc is not None
        assert plan_doc.content == "Plan for Initial Title"

        tech_spec_doc = self.fake_tech_spec_doc_repo.get_by_project_id(proj.project_id)
        assert tech_spec_doc is not None
        assert tech_spec_doc.content == "Spec for Initial Title"

    def test_update_project_not_found(self):
        """PUT /projects/{project_id} (存在しないID) のテスト"""
        non_existent_id = self.fake_project_repo._generate_id()
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
        mock_project_repo.get_by_id.return_value = proj
        mock_project_repo.save_or_update.side_effect = Exception(
            "Database error on update"
        )
        app.dependency_overrides[get_project_repository] = lambda: mock_project_repo

        response = self.client.put(
            f"/projects/{proj.project_id}",
            json={"title": "Update Fail"},
        )

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        data = response.json()
        assert "detail" in data
        assert "Failed to update project: Database error on update" in data["detail"]

        del app.dependency_overrides[get_project_repository]

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

        plan_doc = self.fake_plan_doc_repo.get_by_project_id(project_id)
        assert plan_doc is not None

        tech_spec_doc = self.fake_tech_spec_doc_repo.get_by_project_id(project_id)
        assert tech_spec_doc is not None

    def test_delete_project_not_found(self):
        """DELETE /projects/{project_id} (存在しないID) のテスト"""
        non_existent_id = self.fake_project_repo._generate_id()

        response = self.client.delete(f"/projects/{non_existent_id}")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert "detail" in data
        assert f"Project with ID '{non_existent_id}' not found" in data["detail"]

    def test_delete_project_failure(self):
        """DELETE /projects/{project_id} (リポジトリ失敗時) のテスト"""
        proj = self._create_project_in_repo("Project To Fail Delete", create_docs=True)
        mock_project_repo = MagicMock(spec=ProjectRepository)
        mock_project_repo.delete_by_id.side_effect = Exception(
            "Database error on delete"
        )
        app.dependency_overrides[get_project_repository] = lambda: mock_project_repo

        response = self.client.delete(f"/projects/{proj.project_id}")

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        data = response.json()
        assert "detail" in data
        assert "Failed to delete project: Database error on delete" in data["detail"]

        del app.dependency_overrides[get_project_repository]
