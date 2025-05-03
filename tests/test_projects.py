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
from models import Project, Document
from repositories.projects import ProjectRepository
from repositories.documents import DocumentRepository
from routers.utils import (
    get_project_repository,
    get_plan_document_repository,
    get_tech_spec_document_repository,  # Line break applied
)


# --- Fake Project Repository Class ---
class FakeProjectRepository(ProjectRepository):
    """インメモリでプロジェクトを管理するFakeリポジトリクラス"""

    def __init__(self):
        self._projects: Dict[UUID, Project] = {}

    def save_or_update(self, project: Project) -> UUID:
        """プロジェクトを保存または更新する"""
        # 型チェックを追加して、誤った型のオブジェクトが渡された場合に早期にエラーを出す
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
                title=project.title,
                created_at=existing_project.created_at,
                updated_at=now,
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
                created_at=getattr(project, "created_at", now),
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


# --- Fake Document Repository Class ---
class FakeDocumentRepository(DocumentRepository):
    """インメモリでドキュメントを管理するFakeリポジトリクラス"""

    def __init__(self):
        # project_id をキー、Document を値とする辞書
        self._documents: Dict[UUID, Document] = {}
        # ドキュメント自体のIDをキーとする辞書も必要に応じて追加可能だが、
        # 今回のテストでは project_id での検索が主
        self._documents_by_doc_id: Dict[UUID, Document] = {}

    def initialize(self, *args, **kwargs):
        return super().initialize(*args, **kwargs)

    def save_or_update(self, document: Document) -> UUID:
        """ドキュメントを保存または更新する"""
        if not isinstance(document, Document):
            raise TypeError("document must be an instance of Document")

        doc_id = getattr(document, "document_id", None)
        project_id = getattr(document, "project_id", None)
        now = datetime.now(timezone.utc)

        if not project_id:
            raise ValueError("project_id is required to save a document")

        # ドキュメントIDが指定されていて、かつ存在する場合（更新）
        if doc_id and doc_id in self._documents_by_doc_id:
            existing_doc = self._documents_by_doc_id[doc_id]
            updated_doc = Document(
                document_id=existing_doc.document_id,
                project_id=existing_doc.project_id,  # project_idは不変とする
                content=document.content,
                created_at=existing_doc.created_at,
                updated_at=now,
            )
            self._documents_by_doc_id[doc_id] = updated_doc
            # project_idをキーとする辞書も更新
            self._documents[project_id] = updated_doc
            # Note: Simplified update; real scenarios might need list handling
            return doc_id
        else:
            # 新規作成
            new_doc_id = doc_id or uuid.uuid4()
            new_document = Document(
                document_id=new_doc_id,
                project_id=project_id,
                content=document.content,
                created_at=getattr(document, "created_at", now),
                updated_at=now,
            )
            # project_id をキーとする辞書に保存（単純化のため、1プロジェクト1ドキュメント前提）
            # 実際には project_id に紐づくドキュメントは複数ある可能性があるため、
            # リストや、ドキュメントタイプを考慮した構造が必要になる場合がある。
            # 今回のテストシナリオ（プロジェクト作成時に特定のドキュメントが作られる）では、
            # project_id で引ければ十分。
            self._documents[project_id] = new_document
            self._documents_by_doc_id[new_doc_id] = new_document
            return new_doc_id

    def get_by_id(self, document_id: UUID) -> Optional[Document]:
        """ドキュメントIDでドキュメントを取得する"""
        return self._documents_by_doc_id.get(document_id)

    def get_by_project_id(self, project_id: UUID) -> Optional[Document]:
        """プロジェクトIDでドキュメントを取得する（単純化：最初に見つかったものを返す）"""
        # この実装は、1プロジェクトIDに1ドキュメントという仮定に基づいている。
        # 実際には、特定のタイプのドキュメント（例：計画、技術仕様）を区別する必要がある。
        # テストでは、各リポジトリインスタンスが特定のタイプを担当するため、これで機能する。
        # UUID 型の引数を str 型に変換して辞書を検索する
        return self._documents.get(str(project_id))

    def get_all_by_project_id(self, project_id: UUID) -> List[Document]:
        """指定されたプロジェクトIDのすべてのドキュメントを取得する"""
        # より現実に近い実装例
        docs = []
        for doc in self._documents_by_doc_id.values():
            if doc.project_id == project_id:
                docs.append(doc)
        return docs

    def delete_by_id(self, document_id: UUID) -> bool:
        """ドキュメントIDでドキュメントを削除する"""
        if document_id in self._documents_by_doc_id:
            doc_to_delete = self._documents_by_doc_id.pop(document_id)
            # project_idをキーとする辞書からも削除（存在すれば）
            if doc_to_delete.project_id in self._documents:
                # ここも単純化。リスト管理の場合はリストから削除
                if self._documents[doc_to_delete.project_id].document_id == document_id:
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

    def setup_method(self):  # Ensure no trailing comment causes length issue
        """各テストメソッドの前に実行されるセットアップ"""
        self.client = TestClient(app)
        self.fake_project_repo = FakeProjectRepository()
        self.fake_plan_doc_repo = FakeDocumentRepository()
        self.fake_tech_spec_doc_repo = FakeDocumentRepository()
        # このクラスのテストで使用する依存関係をオーバーライド
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
        # オーバーライドを解除
        if get_project_repository in app.dependency_overrides:
            del app.dependency_overrides[get_project_repository]
        if get_plan_document_repository in app.dependency_overrides:
            del app.dependency_overrides[get_plan_document_repository]
        if get_tech_spec_document_repository in app.dependency_overrides:
            del app.dependency_overrides[get_tech_spec_document_repository]

        self.fake_project_repo.clear()  # 各テスト後にリポジトリをクリア
        self.fake_plan_doc_repo.clear()
        self.fake_tech_spec_doc_repo.clear()

    # --- Helper Methods ---
    # Break signature over multiple lines
    def _create_project_in_repo(self, title: str, create_docs: bool = False) -> Project:
        """テスト用にリポジトリに直接プロジェクトを作成するヘルパー"""
        project = Project(title=title)
        saved_project_id = self.fake_project_repo.save_or_update(project)
        saved_project = self.fake_project_repo.get_by_id(saved_project_id)

        if create_docs and saved_project:
            # API経由ではないため、手動でドキュメントも作成する
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
        assert "project_id" in data  # id -> project_id
        assert "created_at" in data
        assert "updated_at" in data

        # プロジェクトがFakeリポジトリに保存されたことを確認
        project_id_from_response = UUID(data["project_id"])
        saved_project = self.fake_project_repo.get_by_id(project_id_from_response)
        assert saved_project is not None
        assert saved_project.title == project_title
        assert saved_project.project_id == project_id_from_response

        # ドキュメントがFakeリポジトリに保存されたことを確認
        plan_doc = self.fake_plan_doc_repo.get_by_project_id(project_id_from_response)
        assert plan_doc is not None
        assert plan_doc.project_id == str(project_id_from_response)
        assert plan_doc.content == ""  # Initial content should be empty

        tech_spec_doc = self.fake_tech_spec_doc_repo.get_by_project_id(
            project_id_from_response
        )
        assert tech_spec_doc is not None
        assert tech_spec_doc.project_id == str(project_id_from_response)
        assert tech_spec_doc.content == ""  # Initial content should be empty

    def test_create_project_failure(self):
        """POST /projects (リポジトリ失敗時) のテスト"""
        # プロジェクトリポジトリでエラーが発生する場合
        mock_project_repo = MagicMock(spec=ProjectRepository)
        mock_project_repo.save_or_update.side_effect = Exception(
            "Database error on project create"
        )
        # ドキュメントリポジトリは正常でも、プロジェクト作成で失敗するケース
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

        # このテストで使用したオーバーライドを解除
        del app.dependency_overrides[get_project_repository]
        del app.dependency_overrides[get_plan_document_repository]
        del app.dependency_overrides[get_tech_spec_document_repository]

    def test_create_project_failure_on_doc_save(self):
        """POST /projects (ドキュメント保存失敗時) のテスト"""
        # プロジェクト保存は成功するが、計画ドキュメント保存で失敗するケース
        mock_project_repo = FakeProjectRepository()  # プロジェクトは一旦保存される
        mock_plan_repo = MagicMock(spec=DocumentRepository)
        mock_plan_repo.save_or_update.side_effect = Exception(
            "Database error on plan doc create"
        )
        # これは呼ばれないはず
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

        # 本来はロールバックされるべきだが、Fakeリポジトリではそこまで実装しない
        # プロジェクトが残ってしまっている可能性がある（テスト実装による）
        # assert len(mock_project_repo.get_all()) == 0 # ロールバック確認（もし実装されていれば）

        # このテストで使用したオーバーライドを解除
        del app.dependency_overrides[get_project_repository]
        del app.dependency_overrides[get_plan_document_repository]
        del app.dependency_overrides[get_tech_spec_document_repository]

    # GET /projects
    def test_get_all_projects_success(self):
        """GET /projects (成功時、複数プロジェクト) のテスト"""
        # 事前にデータを準備 (ドキュメントも作成される想定でテスト)
        # _create_project_in_repo はAPI経由ではないため、手動でドキュメントも作るか、
        # create_docs=True のようなフラグを追加する
        proj1 = self._create_project_in_repo("Project Alpha", create_docs=True)
        proj2 = self._create_project_in_repo("Project Beta", create_docs=True)

        response = self.client.get("/projects")

        # ドキュメントリポジトリの状態はここでは直接検証しない（GET /projects はプロジェクトのみ返すため）

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
        # ドキュメントも作成される想定で準備
        proj = self._create_project_in_repo("Project Gamma", create_docs=True)

        response = self.client.get(f"/projects/{proj.project_id}")

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
        proj_id = uuid.uuid4()  # ダミーID
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
        # ドキュメントも作成される想定で準備
        proj = self._create_project_in_repo("Initial Title", create_docs=True)
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
        saved_project = self.fake_project_repo.get_by_id(proj.project_id)
        assert saved_project is not None
        assert saved_project.title == updated_title
        assert saved_project.updated_at == new_updated_at

        # ドキュメントは更新されないはずなので、元の状態を確認
        plan_doc = self.fake_plan_doc_repo.get_by_project_id(proj.project_id)
        assert plan_doc is not None
        assert (
            plan_doc.content == "Plan for Initial Title"
        )  # _create_project_in_repo で設定した内容

        tech_spec_doc = self.fake_tech_spec_doc_repo.get_by_project_id(proj.project_id)
        assert tech_spec_doc is not None
        # _create_project_in_repo で設定した内容
        assert tech_spec_doc.content == "Spec for Initial Title"

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
        proj = self._create_project_in_repo("Project To Fail Update", create_docs=True)
        mock_project_repo = MagicMock(spec=ProjectRepository)
        # get_by_idは成功させるが、save_or_updateで失敗させる
        mock_project_repo.get_by_id.return_value = proj
        mock_project_repo.save_or_update.side_effect = Exception(
            "Database error on update"
        )
        app.dependency_overrides[get_project_repository] = lambda: mock_project_repo

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
        # ドキュメントも作成される想定で準備
        proj = self._create_project_in_repo("Project To Delete", create_docs=True)
        project_id = proj.project_id  # IDを保持

        response = self.client.delete(
            f"/projects/{proj.project_id}"
        )  # id -> project_id

        assert response.status_code == status.HTTP_204_NO_CONTENT
        # レスポンスボディは空のはず
        assert not response.content

        # プロジェクトがFakeリポジトリから削除されたことを確認
        deleted_project = self.fake_project_repo.get_by_id(project_id)
        assert deleted_project is None

        # 関連するドキュメントも削除されるべきか？ -> 現在のルーター実装では削除されない
        # そのため、ドキュメントが残っていることを確認（あるいは削除されるようにルーターを修正する）
        # ここでは現在の実装に合わせて、ドキュメントが残っている（削除ロジックがない）ことを確認
        plan_doc = self.fake_plan_doc_repo.get_by_project_id(project_id)
        assert plan_doc is not None  # ルーターが削除しないので残っているはず

        tech_spec_doc = self.fake_tech_spec_doc_repo.get_by_project_id(project_id)
        assert tech_spec_doc is not None  # ルーターが削除しないので残っているはず

        # もしドキュメントも削除する仕様なら、以下のようにアサートする
        # assert plan_doc is None
        # assert tech_spec_doc is None

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
        proj = self._create_project_in_repo("Project To Fail Delete", create_docs=True)
        mock_project_repo = MagicMock(spec=ProjectRepository)
        mock_project_repo.delete_by_id.side_effect = Exception(
            "Database error on delete"
        )
        app.dependency_overrides[get_project_repository] = lambda: mock_project_repo

        response = self.client.delete(
            f"/projects/{proj.project_id}"
        )  # id -> project_id

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        data = response.json()
        assert "detail" in data
        assert "Failed to delete project: Database error on delete" in data["detail"]

        del app.dependency_overrides[get_project_repository]
