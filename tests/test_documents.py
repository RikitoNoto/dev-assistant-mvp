from fastapi.testclient import TestClient
from typing import TYPE_CHECKING
from unittest.mock import MagicMock


if TYPE_CHECKING:
    from src.api import app
    from src.models.document import Document
    from src.repositories.documents import DocumentRepository
else:
    from api import app
    from models.document import Document
    from repositories.documents import DocumentRepository


# --- Fake リポジトリクラス (変更なし) ---
class FakeDocumentRepository(DocumentRepository):
    """インメモリでドキュメントを管理するFakeリポジトリクラス"""

    def __init__(self):
        self._documents = {}

    def save_or_update(self, document: Document) -> str:
        if not isinstance(document, Document):
            raise TypeError("document must be an instance of Document")
        if not document.project_id:
            raise ValueError("project_id is required")
        self._documents[document.project_id] = document
        # APIルーターが返すIDと一致させるため、元のproject_idを返す
        return document.project_id

    def get_by_id(self, document_id: str) -> Document | None:
        # ルーターで使用されているメソッドを追加
        return self._documents.get(document_id)

    def clear(self):
        self._documents = {}

    def initialize(self, *args, **kwargs):
        return super().initialize(*args, **kwargs)


# --- テストクラス ---


class TestPlanningDocumentAPI:
    """Planning Document API (/documents/plan) のテストクラス"""

    def setup_method(self):
        """各テストメソッドの前に実行されるセットアップ"""
        self.client = TestClient(app)
        self.fake_repo = FakeDocumentRepository()
        # モデルに直接リポジトリを設定
        Document.set_repository(self.fake_repo)

    def teardown_method(self):
        """各テストメソッドの後に実行されるクリーンアップ"""
        # リポジトリをクリア
        self.fake_repo.clear()

    def save_or_update(
        self,
        content: str,
        project_id: str,  # project_id は必須に変更
        status_code: int = 200,
    ) -> dict:
        """APIを呼び出すヘルパーメソッド"""
        # project_id は常に渡される想定
        document_data = {"project_id": project_id, "content": content}
        response = self.client.post("/documents/plan", json=document_data)
        assert response.status_code == status_code
        return response.json()

    def get(self, project_id: str, status_code: int = 200) -> dict:
        """APIを呼び出すヘルパーメソッド"""
        response = self.client.get(f"/documents/plan/{project_id}")
        assert response.status_code == status_code
        return response.json()

    def test_save_or_update_planning_document_create(self):
        """POST /documents/plan (新規作成時) のテスト"""
        project_id = "plan-proj-create-class"
        content = "New planning content in class"

        data = self.save_or_update(content=content, project_id=project_id)

        assert data == {"project_id": project_id, "status": "success"}

        saved_document = self.fake_repo.get_by_id(project_id)
        assert saved_document is not None
        assert saved_document.project_id == project_id
        assert saved_document.content == content

    def test_save_or_update_planning_document_update(self):
        """POST /documents/plan (更新時) のテスト"""
        project_id = "plan-proj-update-class"
        initial_content = "Initial plan in class"
        updated_content = "Updated planning content in class"

        # 事前にドキュメントを作成しておく
        initial_doc = Document(project_id=project_id, content=initial_content)
        self.fake_repo.save_or_update(initial_doc)

        data = self.save_or_update(content=updated_content, project_id=project_id)

        assert data == {"project_id": project_id, "status": "success"}

        # アサーション (Fakeリポジトリの状態)
        saved_document = self.fake_repo.get_by_id(project_id)
        assert saved_document is not None
        assert saved_document.project_id == project_id
        assert saved_document.content == updated_content

    def test_save_or_update_planning_document_failure(self):
        """POST /documents/plan (リポジトリ失敗時) のテスト"""
        # save_or_updateが例外を発生させるリポジトリのモックを作成
        mock_repo = MagicMock(spec=DocumentRepository)
        mock_repo.save_or_update.side_effect = Exception("Database error for plan")
        # モデルに直接モックリポジトリを設定
        Document.set_repository(mock_repo)

        data = self.save_or_update(
            content="Content",
            project_id="plan-proj-fail-class",
            status_code=500,
        )

        assert "detail" in data
        assert "Database error for plan" in data["detail"]
        # テスト後に元のリポジトリに戻す
        Document.set_repository(self.fake_repo)

    # --- GET Tests for Planning Document ---

    def test_get_planning_document_success(self):
        """GET /documents/plan/{project_id} (成功時) のテスト"""
        project_id = "plan-proj-get-success"
        content = "Planning content to get"
        doc = Document(project_id=project_id, content=content)
        self.fake_repo.save_or_update(doc)  # 事前にデータを保存
        data = self.get(project_id=project_id)
        assert data["project_id"] == project_id
        assert data["content"] == content

    def test_get_planning_document_not_found(self):
        """GET /documents/plan/{project_id} (存在しないID) のテスト"""
        project_id = "plan-proj-get-not-found"
        data = self.get(project_id=project_id, status_code=404)

        assert "detail" in data
        assert f"Document with ID '{project_id}' not found" in data["detail"]

    def test_get_planning_document_failure(self):
        """GET /documents/plan/{project_id} (リポジトリ失敗時) のテスト"""
        project_id = "plan-proj-get-fail"
        # get_by_idが例外を発生させるモックを作成
        mock_repo = MagicMock(spec=DocumentRepository)
        mock_repo.get_by_id.side_effect = Exception("Database error getting plan")
        # モデルに直接モックリポジトリを設定
        Document.set_repository(mock_repo)
        
        data = self.get(project_id=project_id, status_code=500)
        assert "detail" in data
        assert "Failed to get document: Database error getting plan" in data["detail"]

        # テスト後に元のリポジトリに戻す
        Document.set_repository(self.fake_repo)


class TestTechSpecDocumentAPI:
    """Tech Spec Document API (/documents/tech-spec) のテストクラス"""

    def setup_method(self):
        """各テストメソッドの前に実行されるセットアップ"""
        self.client = TestClient(app)
        self.fake_repo = FakeDocumentRepository()
        # モデルに直接リポジトリを設定
        Document.set_repository(self.fake_repo)

    def teardown_method(self):
        """各テストメソッドの後に実行されるクリーンアップ"""
        # リポジトリをクリア
        self.fake_repo.clear()

    def save_or_update(
        self,
        content: str,
        project_id: str,  # project_id は必須に変更
        status_code: int = 200,
    ) -> dict:
        """APIを呼び出すヘルパーメソッド"""
        # project_id は常に渡される想定
        document_data = {"project_id": project_id, "content": content}
        response = self.client.post("/documents/tech-spec", json=document_data)
        assert response.status_code == status_code
        return response.json()

    def get(self, project_id: str, status_code: int = 200) -> dict:
        """APIを呼び出すヘルパーメソッド"""
        response = self.client.get(f"/documents/tech-spec/{project_id}")
        assert response.status_code == status_code
        return response.json()

    def test_save_or_update_tech_spec_document_create(self):
        """POST /documents/tech-spec (新規作成時) のテスト"""
        project_id = "tech-proj-create-class"
        content = "New tech spec content in class"
        data = self.save_or_update(content=content, project_id=project_id)

        assert data == {"project_id": project_id, "status": "success"}

        # アサーション (Fakeリポジトリの状態)
        saved_document = self.fake_repo.get_by_id(project_id)
        assert saved_document is not None
        assert saved_document.project_id == project_id
        assert saved_document.content == content

    def test_save_or_update_tech_spec_document_update(self):
        """POST /documents/tech-spec (更新時) のテスト"""
        project_id = "tech-proj-update-class"
        initial_content = "Initial tech spec in class"
        updated_content = "Updated tech spec content in class"

        # 事前にドキュメントを作成しておく
        initial_doc = Document(project_id=project_id, content=initial_content)
        self.fake_repo.save_or_update(initial_doc)

        data = self.save_or_update(content=updated_content, project_id=project_id)
        assert data == {"project_id": project_id, "status": "success"}

        # アサーション (Fakeリポジトリの状態)
        saved_document = self.fake_repo.get_by_id(project_id)
        assert saved_document is not None
        assert saved_document.project_id == project_id
        assert saved_document.content == updated_content

    def test_save_or_update_tech_spec_document_failure(self):
        """POST /documents/tech-spec (リポジトリ失敗時) のテスト"""
        # save_or_updateが例外を発生させるリポジトリのモックを作成
        mock_repo = MagicMock(spec=DocumentRepository)
        mock_repo.save_or_update.side_effect = Exception("Database error for tech-spec")
        # モデルに直接モックリポジトリを設定
        Document.set_repository(mock_repo)

        data = self.save_or_update(
            content="Content",
            project_id="tech-proj-fail-class",
            status_code=500,
        )
        assert "detail" in data
        assert "Database error for tech-spec" in data["detail"]

        # テスト後に元のリポジトリに戻す
        Document.set_repository(self.fake_repo)

    # --- GET Tests for Tech Spec Document ---

    def test_get_tech_spec_document_success(self):
        """GET /documents/tech-spec/{project_id} (成功時) のテスト"""
        project_id = "tech-proj-get-success"
        content = "Tech spec content to get"
        doc = Document(project_id=project_id, content=content)
        self.fake_repo.save_or_update(doc)  # 事前にデータを保存

        data = self.get(project_id=project_id)

        assert data["project_id"] == project_id
        assert data["content"] == content

    def test_get_tech_spec_document_not_found(self):
        """GET /documents/tech-spec/{project_id} (存在しないID) のテスト"""
        project_id = "tech-proj-get-not-found"

        data = self.get(project_id=project_id, status_code=404)
        assert "detail" in data
        assert f"Document with ID '{project_id}' not found" in data["detail"]

    def test_get_tech_spec_document_failure(self):
        """GET /documents/tech-spec/{project_id} (リポジトリ失敗時) のテスト"""
        project_id = "tech-proj-get-fail"
        # get_by_idが例外を発生させるモックを作成
        mock_repo = MagicMock(spec=DocumentRepository)
        mock_repo.get_by_id.side_effect = Exception("Database error getting tech-spec")
        # モデルに直接モックリポジトリを設定
        Document.set_repository(mock_repo)
        
        data = self.get(project_id=project_id, status_code=500)
        assert "detail" in data
        assert (
            "Failed to get document: Database error getting tech-spec" in data["detail"]
        )

        # テスト後に元のリポジトリに戻す
        Document.set_repository(self.fake_repo)
