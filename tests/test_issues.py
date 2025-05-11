from fastapi.testclient import TestClient
from unittest.mock import MagicMock
from datetime import datetime
import uuid

# テスト対象のFastAPIアプリケーションをインポート
from api import app
from models.models import Issue
from repositories.issues import (
    IssueRepository,
)  # Fakeが継承するため、またはモックのspec用
from routers.utils import get_issue_repository


# --- Fake リポジトリクラス ---
class FakeIssueRepository(IssueRepository):
    """インメモリでIssueを管理するFakeリポジトリクラス"""

    def __init__(self):
        self._issues = {}  # {project_id: {issue_id: Issue}}

    def initialize(self, *args, **kwargs):
        return super().initialize(*args, **kwargs)

    def save_or_update(self, issue: Issue) -> str:
        if not isinstance(issue, Issue):
            raise TypeError("issue must be an instance of Issue")
        if not issue.project_id:
            raise ValueError("project_id is required")
        
        # プロジェクトIDに対応する辞書がなければ作成
        if issue.project_id not in self._issues:
            self._issues[issue.project_id] = {}
        
        # Issueを保存
        self._issues[issue.project_id][issue.issue_id] = issue
        return issue.issue_id

    def get_by_id(self, project_id: str, issue_id: str) -> Issue | None:
        if project_id not in self._issues:
            return None
        return self._issues[project_id].get(issue_id)

    def get_by_project_id(self, project_id: str) -> list[Issue]:
        if project_id not in self._issues:
            return []
        return list(self._issues[project_id].values())

    def delete(self, project_id: str, issue_id: str) -> None:
        if project_id in self._issues and issue_id in self._issues[project_id]:
            del self._issues[project_id][issue_id]

    def clear(self):
        self._issues = {}


# --- テストクラス ---
class TestIssueAPI:
    """Issue API (/issues) のテストクラス"""

    def setup_method(self):
        """各テストメソッドの前に実行されるセットアップ"""
        self.client = TestClient(app)
        self.fake_repo = FakeIssueRepository()
        # このクラスのテストで使用する依存関係をオーバーライド
        app.dependency_overrides[get_issue_repository] = lambda: self.fake_repo

    def teardown_method(self):
        """各テストメソッドの後に実行されるクリーンアップ"""
        # オーバーライドを解除
        if get_issue_repository in app.dependency_overrides:
            del app.dependency_overrides[get_issue_repository]
        self.fake_repo.clear()

    def create_issue(
        self,
        title: str,
        project_id: str,
        description: str = "",
        status: str = "todo",
        status_code: int = 200,
    ) -> dict:
        """APIを呼び出すヘルパーメソッド - Issue作成"""
        issue_data = {
            "project_id": project_id,
            "title": title,
            "description": description,
            "status": status,
        }
        response = self.client.post("/issues/", json=issue_data)
        assert response.status_code == status_code
        return response.json()

    def get_issue(self, project_id: str, issue_id: str, status_code: int = 200) -> dict:
        """APIを呼び出すヘルパーメソッド - Issue取得"""
        response = self.client.get(f"/issues/{project_id}/{issue_id}")
        assert response.status_code == status_code
        return response.json()

    def get_issues_by_project(
        self, project_id: str, status: str = None, status_code: int = 200
    ) -> list:
        """APIを呼び出すヘルパーメソッド - プロジェクト別Issue一覧取得"""
        url = f"/issues/{project_id}"
        if status:
            url += f"?status={status}"
        response = self.client.get(url)
        assert response.status_code == status_code
        return response.json()

    def delete_issue(
        self, project_id: str, issue_id: str, status_code: int = 200
    ) -> dict:
        """APIを呼び出すヘルパーメソッド - Issue削除"""
        response = self.client.delete(f"/issues/{project_id}/{issue_id}")
        assert response.status_code == status_code
        return response.json()

    # --- POST Tests ---
    def test_save_or_update_issue_create(self):
        """POST /issues/ (新規作成時) のテスト"""
        project_id = "test-project-1"
        title = "Test Issue"
        description = "This is a test issue"
        status = "todo"

        data = self.create_issue(
            title=title, project_id=project_id, description=description, status=status
        )

        assert "issue_id" in data
        assert data["project_id"] == project_id
        assert data["status"] == "success"

        # Fakeリポジトリから取得して検証
        issue_id = data["issue_id"]
        saved_issue = self.fake_repo.get_by_id(project_id, issue_id)
        assert saved_issue is not None
        assert saved_issue.project_id == project_id
        assert saved_issue.title == title
        assert saved_issue.description == description
        assert saved_issue.status == status

    def test_save_or_update_issue_update(self):
        """POST /issues/ (更新時) のテスト"""
        # 事前にIssueを作成
        project_id = "test-project-2"
        initial_title = "Initial Issue"
        initial_description = "Initial description"
        initial_status = "todo"

        # 新規作成
        initial_data = self.create_issue(
            title=initial_title,
            project_id=project_id,
            description=initial_description,
            status=initial_status,
        )
        issue_id = initial_data["issue_id"]

        # 更新データ
        updated_title = "Updated Issue"
        updated_description = "Updated description"
        updated_status = "in_progress"

        # 更新用のIssueオブジェクトを作成
        update_issue_data = {
            "issue_id": issue_id,
            "project_id": project_id,
            "title": updated_title,
            "description": updated_description,
            "status": updated_status,
        }
        response = self.client.post("/issues/", json=update_issue_data)
        assert response.status_code == 200
        data = response.json()

        assert data["issue_id"] == issue_id
        assert data["project_id"] == project_id
        assert data["status"] == "success"

        # 更新されたIssueを取得して検証
        updated_issue = self.fake_repo.get_by_id(project_id, issue_id)
        assert updated_issue is not None
        assert updated_issue.project_id == project_id
        assert updated_issue.title == updated_title
        assert updated_issue.description == updated_description
        assert updated_issue.status == updated_status

    def test_save_or_update_issue_failure(self):
        """POST /issues/ (リポジトリ失敗時) のテスト"""
        # save_or_updateが例外を発生させるリポジトリのモックを作成
        mock_repo = MagicMock(spec=IssueRepository)
        mock_repo.save_or_update.side_effect = Exception("Database error for issue")
        # このテスト専用のオーバーライドを設定
        app.dependency_overrides[get_issue_repository] = lambda: mock_repo

        data = self.create_issue(
            title="Failing Issue",
            project_id="test-project-fail",
            status_code=500,
        )

        assert "detail" in data
        assert "Failed to save/update issue: Database error for issue" in data["detail"]
        # このテストで使用したオーバーライドを明示的に解除
        del app.dependency_overrides[get_issue_repository]

    # --- GET Tests for Single Issue ---
    def test_get_issue_success(self):
        """GET /issues/{project_id}/{issue_id} (成功時) のテスト"""
        # 事前にIssueを作成
        project_id = "test-project-3"
        title = "Test Issue for Get"
        description = "This is a test issue for get"
        status = "todo"

        data = self.create_issue(
            title=title, project_id=project_id, description=description, status=status
        )
        issue_id = data["issue_id"]

        # Issueを取得
        issue_data = self.get_issue(project_id=project_id, issue_id=issue_id)

        assert issue_data["issue_id"] == issue_id
        assert issue_data["project_id"] == project_id
        assert issue_data["title"] == title
        assert issue_data["description"] == description
        assert issue_data["status"] == status

    def test_get_issue_not_found(self):
        """GET /issues/{project_id}/{issue_id} (存在しないID) のテスト"""
        project_id = "test-project-not-exist"
        issue_id = "non-existent-issue"
        data = self.get_issue(
            project_id=project_id, issue_id=issue_id, status_code=404
        )

        assert "detail" in data
        assert f"Issue with ID '{issue_id}' not found in project '{project_id}'" in data["detail"]

    def test_get_issue_failure(self):
        """GET /issues/{project_id}/{issue_id} (リポジトリ失敗時) のテスト"""
        project_id = "test-project-get-fail"
        issue_id = "test-issue-get-fail"
        # get_by_idが例外を発生させるモックを作成
        mock_repo = MagicMock(spec=IssueRepository)
        mock_repo.get_by_id.side_effect = Exception("Database error getting issue")
        # このテスト専用のオーバーライドを設定
        app.dependency_overrides[get_issue_repository] = lambda: mock_repo
        
        data = self.get_issue(
            project_id=project_id, issue_id=issue_id, status_code=500
        )
        
        assert "detail" in data
        assert "Failed to get issue: Database error getting issue" in data["detail"]

        # このテストで使用したオーバーライドを明示的に解除
        del app.dependency_overrides[get_issue_repository]

    # --- GET Tests for Project Issues ---
    def test_get_issues_by_project_success(self):
        """GET /issues/{project_id} (成功時) のテスト"""
        project_id = "test-project-4"
        
        # 複数のIssueを作成
        issue1_data = self.create_issue(
            title="Issue 1", project_id=project_id, status="todo"
        )
        issue2_data = self.create_issue(
            title="Issue 2", project_id=project_id, status="in_progress"
        )
        issue3_data = self.create_issue(
            title="Issue 3", project_id=project_id, status="todo"
        )
        
        # プロジェクトの全Issueを取得
        issues = self.get_issues_by_project(project_id=project_id)
        
        assert len(issues) == 3
        issue_ids = [issue["issue_id"] for issue in issues]
        assert issue1_data["issue_id"] in issue_ids
        assert issue2_data["issue_id"] in issue_ids
        assert issue3_data["issue_id"] in issue_ids

    def test_get_issues_by_project_with_status_filter(self):
        """GET /issues/{project_id}?status={status} (ステータスフィルタ付き) のテスト"""
        project_id = "test-project-5"
        
        # 異なるステータスのIssueを作成
        self.create_issue(title="Todo Issue 1", project_id=project_id, status="todo")
        self.create_issue(title="Todo Issue 2", project_id=project_id, status="todo")
        self.create_issue(title="In Progress Issue", project_id=project_id, status="in_progress")
        self.create_issue(title="Done Issue", project_id=project_id, status="done")
        
        # todoステータスのIssueのみを取得
        todo_issues = self.get_issues_by_project(project_id=project_id, status="todo")
        assert len(todo_issues) == 2
        for issue in todo_issues:
            assert issue["status"] == "todo"
        
        # in_progressステータスのIssueのみを取得
        in_progress_issues = self.get_issues_by_project(project_id=project_id, status="in_progress")
        assert len(in_progress_issues) == 1
        assert in_progress_issues[0]["status"] == "in_progress"

    def test_get_issues_by_project_empty(self):
        """GET /issues/{project_id} (Issueが存在しない場合) のテスト"""
        project_id = "test-project-empty"
        issues = self.get_issues_by_project(project_id=project_id)
        assert len(issues) == 0

    def test_get_issues_by_project_failure(self):
        """GET /issues/{project_id} (リポジトリ失敗時) のテスト"""
        project_id = "test-project-list-fail"
        # get_by_project_idが例外を発生させるモックを作成
        mock_repo = MagicMock(spec=IssueRepository)
        mock_repo.get_by_project_id.side_effect = Exception("Database error listing issues")
        # このテスト専用のオーバーライドを設定
        app.dependency_overrides[get_issue_repository] = lambda: mock_repo
        
        # status引数を指定せず、status_codeのみを指定
        response = self.client.get(f"/issues/{project_id}")
        assert response.status_code == 500
        data = response.json()
        
        assert "detail" in data
        assert "Failed to get issues for project: Database error listing issues" in data["detail"]

        # このテストで使用したオーバーライドを明示的に解除
        del app.dependency_overrides[get_issue_repository]

    # --- DELETE Tests ---
    def test_delete_issue_success(self):
        """DELETE /issues/{project_id}/{issue_id} (成功時) のテスト"""
        # 事前にIssueを作成
        project_id = "test-project-6"
        title = "Test Issue for Delete"
        
        data = self.create_issue(title=title, project_id=project_id)
        issue_id = data["issue_id"]
        
        # Issueが存在することを確認
        issue = self.fake_repo.get_by_id(project_id, issue_id)
        assert issue is not None
        
        # Issueを削除
        delete_data = self.delete_issue(project_id=project_id, issue_id=issue_id)
        
        assert delete_data["status"] == "success"
        assert "Issue" in delete_data["message"]
        assert "deleted successfully" in delete_data["message"]
        
        # Issueが削除されたことを確認
        deleted_issue = self.fake_repo.get_by_id(project_id, issue_id)
        assert deleted_issue is None

    def test_delete_issue_not_found(self):
        """DELETE /issues/{project_id}/{issue_id} (存在しないID) のテスト"""
        project_id = "test-project-not-exist-delete"
        issue_id = "non-existent-issue-delete"
        
        data = self.delete_issue(
            project_id=project_id, issue_id=issue_id, status_code=404
        )
        
        assert "detail" in data
        assert f"Issue with ID '{issue_id}' not found in project '{project_id}'" in data["detail"]

    def test_delete_issue_failure(self):
        """DELETE /issues/{project_id}/{issue_id} (リポジトリ失敗時) のテスト"""
        # 事前にIssueを作成
        project_id = "test-project-7"
        title = "Test Issue for Delete Failure"
        
        data = self.create_issue(title=title, project_id=project_id)
        issue_id = data["issue_id"]
        
        # deleteが例外を発生させるモックを作成
        mock_repo = MagicMock(spec=IssueRepository)
        # get_by_idは成功するがdeleteで失敗するようにする
        mock_repo.get_by_id.return_value = Issue(
            issue_id=issue_id,
            project_id=project_id,
            title=title,
        )
        mock_repo.delete.side_effect = Exception("Database error deleting issue")
        
        # このテスト専用のオーバーライドを設定
        app.dependency_overrides[get_issue_repository] = lambda: mock_repo
        
        data = self.delete_issue(
            project_id=project_id, issue_id=issue_id, status_code=500
        )
        
        assert "detail" in data
        assert "Failed to delete issue: Database error deleting issue" in data["detail"]
        
        # このテストで使用したオーバーライドを明示的に解除
        del app.dependency_overrides[get_issue_repository]
