import time
from fastapi.testclient import TestClient
from unittest.mock import MagicMock
from datetime import datetime
from typing import Dict, List, Optional, TYPE_CHECKING, Any
import random
import string
from fastapi import status

# テスト対象のFastAPIアプリケーションをインポート
if TYPE_CHECKING:
    from src.api import app
    from src.models.issue import Issue
    from src.repositories.issues import IssueRepository
    from src.routers.utils import get_issue_repository
else:
    from api import app
    from models.issue import Issue
    from repositories.issues import IssueRepository
    from routers.utils import get_issue_repository


# --- Fake リポジトリクラス ---
class FakeIssueRepository(IssueRepository):
    """インメモリでIssueを管理するFakeリポジトリクラス"""

    def __init__(self):
        self._issues = {}  # {project_id: {issue_id: Issue}}

    def _generate_id(self) -> str:
        """テスト用のランダムな文字列IDを生成する"""
        return "".join(random.choices(string.ascii_lowercase + string.digits, k=12))

    def initialize(self, *args, **kwargs):
        return super().initialize(*args, **kwargs)

    def save_or_update(self, issue_data: Dict[str, Any]) -> str:
        if not isinstance(issue_data, dict):
            raise TypeError("issue_data must be a dictionary")
        if not issue_data.get('project_id'):
            raise ValueError("project_id is required")
        
        # プロジェクトIDに対応する辞書がなければ作成
        project_id = issue_data['project_id']
        issue_id = issue_data['issue_id']
        
        if project_id not in self._issues:
            self._issues[project_id] = {}
        
        # Issueを保存
        self._issues[project_id][issue_id] = issue_data
        return issue_id

    def get_by_id(self, project_id: str, issue_id: str) -> Optional[Dict[str, Any]]:
        if project_id not in self._issues:
            return None
        return self._issues[project_id].get(issue_id)

    def get_by_project_id(self, project_id: str) -> List[Dict[str, Any]]:
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
        # Issueモデルにリポジトリを設定
        Issue.set_repository(self.fake_repo)

    def teardown_method(self):
        """各テストメソッドの後に実行されるクリーンアップ"""
        self.fake_repo.clear()

    # --- Helper Methods ---
    def _create_issue_in_repo(self, title: str, project_id: str, description: str = "", status: str = "todo") -> Issue:
        """テスト用にリポジトリに直接Issueを作成するヘルパー"""
        issue = Issue(
            project_id=project_id,
            title=title,
            description=description,
            status=status
        )
        issue.create()
        return issue

    def _create_issue_via_api(self, title: str, project_id: str, description: str = "", status: str = "todo", expected_status: int = status.HTTP_201_CREATED) -> dict:
        """APIを呼び出してIssueを作成するヘルパーメソッド"""
        issue_data = {
            "project_id": project_id,
            "title": title,
            "description": description,
            "status": status,
        }
        response = self.client.post("/issues/", json=issue_data)
        assert response.status_code == expected_status
        return response.json()

    def _get_issue(self, project_id: str, issue_id: str, expected_status: int = status.HTTP_200_OK) -> dict:
        """APIを呼び出してIssueを取得するヘルパーメソッド"""
        response = self.client.get(f"/issues/{project_id}/{issue_id}")
        assert response.status_code == expected_status
        return response.json()

    def _get_issues_by_project(self, project_id: str, status_filter: Optional[str] = None, expected_status: int = status.HTTP_200_OK) -> list:
        """APIを呼び出してプロジェクトの全Issueを取得するヘルパーメソッド"""
        url = f"/issues/{project_id}"
        if status_filter:
            url += f"?status={status_filter}"
        response = self.client.get(url)
        assert response.status_code == expected_status
        return response.json()

    def _update_issue(self, project_id: str, issue_id: str, update_data: dict, expected_status: int = status.HTTP_200_OK) -> dict:
        """APIを呼び出してIssueを更新するヘルパーメソッド"""
        response = self.client.put(f"/issues/{project_id}/{issue_id}", json=update_data)
        assert response.status_code == expected_status
        return response.json()

    def _delete_issue(self, project_id: str, issue_id: str, expected_status: int = status.HTTP_204_NO_CONTENT) -> Optional[dict]:
        """APIを呼び出してIssueを削除するヘルパーメソッド"""
        response = self.client.delete(f"/issues/{project_id}/{issue_id}")
        assert response.status_code == expected_status
        if response.content:
            return response.json()
        return None

    # --- POST Tests ---
    def test_create_issue_success(self):
        """POST /issues/ (新規作成成功時) のテスト"""
        project_id = "test-project-1"
        title = "Test Issue"
        description = "This is a test issue"
        status = "todo"

        data = self._create_issue_via_api(
            title=title, project_id=project_id, description=description, status=status
        )

        assert "issue_id" in data
        assert data["project_id"] == project_id
        assert data["title"] == title
        assert data["description"] == description
        assert data["status"] == status
        assert "created_at" in data
        assert "updated_at" in data

        # リポジトリから取得して検証
        issue_id = data["issue_id"]
        saved_issue = Issue.find_by_id(project_id, issue_id)
        assert saved_issue is not None
        assert saved_issue.project_id == project_id
        assert saved_issue.title == title
        assert saved_issue.description == description
        assert saved_issue.status == status

    def test_update_issue_success(self):
        """PUT /issues/{project_id}/{issue_id} (更新成功時) のテスト"""
        # 事前にIssueを作成
        project_id = "test-project-2"
        initial_title = "Initial Issue"
        initial_description = "Initial description"
        initial_status = "todo"

        # リポジトリに直接作成
        issue = self._create_issue_in_repo(
            title=initial_title,
            project_id=project_id,
            description=initial_description,
            status=initial_status,
        )
        issue_id = issue.issue_id
        original_updated_at = issue.updated_at

        time.sleep(0.01)  # 確実に更新日時が変わるように少し待つ

        # 更新データ
        updated_title = "Updated Issue"
        updated_description = "Updated description"
        updated_status = "in_progress"

        # PUTリクエストで更新
        update_data = {
            "title": updated_title,
            "description": updated_description,
            "status": updated_status,
        }
        updated_data = self._update_issue(project_id, issue_id, update_data)

        assert updated_data["issue_id"] == issue_id
        assert updated_data["project_id"] == project_id
        assert updated_data["title"] == updated_title
        assert updated_data["description"] == updated_description
        assert updated_data["status"] == updated_status
        new_updated_at = datetime.fromisoformat(updated_data["updated_at"])
        assert new_updated_at > original_updated_at

        # 更新されたIssueを取得して検証
        updated_issue = Issue.find_by_id(project_id, issue_id)
        assert updated_issue is not None
        assert updated_issue.project_id == project_id
        assert updated_issue.title == updated_title
        assert updated_issue.description == updated_description
        assert updated_issue.status == updated_status

    def test_create_issue_failure(self):
        """POST /issues/ (リポジトリ失敗時) のテスト"""
        # save_or_updateが例外を発生させるリポジトリのモックを作成
        mock_repo = MagicMock(spec=IssueRepository)
        mock_repo.save_or_update.side_effect = Exception("Database error for issue")
        # Issueモデルにモックリポジトリを設定
        Issue.set_repository(mock_repo)

        response = self.client.post("/issues/", json={
            "project_id": "test-project-fail",
            "title": "Failing Issue",
            "description": "",
            "status": "todo"
        })
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        data = response.json()

        assert "detail" in data
        assert "Failed to create issue: Database error for issue" in data["detail"]
        
        # 元のリポジトリに戻す
        Issue.set_repository(self.fake_repo)

    # --- GET Tests for Single Issue ---
    def test_get_issue_success(self):
        """GET /issues/{project_id}/{issue_id} (成功時) のテスト"""
        # 事前にIssueを作成
        project_id = "test-project-3"
        title = "Test Issue for Get"
        description = "This is a test issue for get"
        status = "todo"

        # リポジトリに直接作成
        issue = self._create_issue_in_repo(
            title=title, project_id=project_id, description=description, status=status
        )
        issue_id = issue.issue_id

        # Issueを取得
        issue_data = self._get_issue(project_id=project_id, issue_id=issue_id)

        assert issue_data["issue_id"] == issue_id
        assert issue_data["project_id"] == project_id
        assert issue_data["title"] == title
        assert issue_data["description"] == description
        assert issue_data["status"] == status
        assert "created_at" in issue_data
        assert "updated_at" in issue_data

    def test_get_issue_not_found(self):
        """GET /issues/{project_id}/{issue_id} (存在しないID) のテスト"""
        project_id = "test-project-not-exist"
        issue_id = "non-existent-issue"
        response = self.client.get(f"/issues/{project_id}/{issue_id}")
        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()

        assert "detail" in data
        assert f"Issue with ID '{issue_id}' not found in project '{project_id}'" in data["detail"]

    def test_get_issue_failure(self):
        """GET /issues/{project_id}/{issue_id} (リポジトリ失敗時) のテスト"""
        project_id = "test-project-get-fail"
        issue_id = "test-issue-get-fail"
        # find_by_idが例外を発生させるモックを作成
        mock_repo = MagicMock(spec=IssueRepository)
        mock_repo.get_by_id.side_effect = Exception("Database error getting issue")
        # Issueモデルにモックリポジトリを設定
        Issue.set_repository(mock_repo)
        
        response = self.client.get(f"/issues/{project_id}/{issue_id}")
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        data = response.json()
        
        assert "detail" in data
        assert "Failed to get issue: Database error getting issue" in data["detail"]

        # 元のリポジトリに戻す
        Issue.set_repository(self.fake_repo)

    # --- GET Tests for Project Issues ---
    def test_get_issues_by_project_success(self):
        """GET /issues/{project_id} (成功時) のテスト"""
        project_id = "test-project-4"
        
        # 複数のIssueを作成
        issue1 = self._create_issue_in_repo(
            title="Issue 1", project_id=project_id, status="todo"
        )
        issue2 = self._create_issue_in_repo(
            title="Issue 2", project_id=project_id, status="in_progress"
        )
        issue3 = self._create_issue_in_repo(
            title="Issue 3", project_id=project_id, status="todo"
        )
        
        # プロジェクトの全Issueを取得
        issues = self._get_issues_by_project(project_id=project_id)
        
        assert len(issues) == 3
        issue_ids = [issue["issue_id"] for issue in issues]
        assert issue1.issue_id in issue_ids
        assert issue2.issue_id in issue_ids
        assert issue3.issue_id in issue_ids

    def test_get_issues_by_project_with_status_filter(self):
        """GET /issues/{project_id}?status={status} (ステータスフィルタ付き) のテスト"""
        project_id = "test-project-5"
        
        # 異なるステータスのIssueを作成
        self._create_issue_in_repo(title="Todo Issue 1", project_id=project_id, status="todo")
        self._create_issue_in_repo(title="Todo Issue 2", project_id=project_id, status="todo")
        self._create_issue_in_repo(title="In Progress Issue", project_id=project_id, status="in_progress")
        self._create_issue_in_repo(title="Done Issue", project_id=project_id, status="done")
        
        # todoステータスのIssueのみを取得
        todo_issues = self._get_issues_by_project(project_id=project_id, status_filter="todo")
        assert len(todo_issues) == 2
        for issue in todo_issues:
            assert issue["status"] == "todo"
        
        # in_progressステータスのIssueのみを取得
        in_progress_issues = self._get_issues_by_project(project_id=project_id, status_filter="in_progress")
        assert len(in_progress_issues) == 1
        assert in_progress_issues[0]["status"] == "in_progress"

    def test_get_issues_by_project_empty(self):
        """GET /issues/{project_id} (Issueが存在しない場合) のテスト"""
        project_id = "test-project-empty"
        issues = self._get_issues_by_project(project_id=project_id)
        assert len(issues) == 0

    def test_get_issues_by_project_failure(self):
        """GET /issues/{project_id} (リポジトリ失敗時) のテスト"""
        project_id = "test-project-list-fail"
        # get_by_project_idが例外を発生させるモックを作成
        mock_repo = MagicMock(spec=IssueRepository)
        mock_repo.get_by_project_id.side_effect = Exception("Database error listing issues")
        # Issueモデルにモックリポジトリを設定
        Issue.set_repository(mock_repo)
        
        response = self.client.get(f"/issues/{project_id}")
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        data = response.json()
        
        assert "detail" in data
        assert "Failed to get issues for project: Database error listing issues" in data["detail"]

        # 元のリポジトリに戻す
        Issue.set_repository(self.fake_repo)

    # --- DELETE Tests ---
    def test_delete_issue_success(self):
        """DELETE /issues/{project_id}/{issue_id} (成功時) のテスト"""
        # 事前にIssueを作成
        project_id = "test-project-6"
        title = "Test Issue for Delete"
        
        issue = self._create_issue_in_repo(title=title, project_id=project_id)
        issue_id = issue.issue_id
        
        # Issueが存在することを確認
        existing_issue = Issue.find_by_id(project_id, issue_id)
        assert existing_issue is not None
        
        # Issueを削除
        self._delete_issue(project_id=project_id, issue_id=issue_id)
        
        # Issueが削除されたことを確認
        deleted_issue = Issue.find_by_id(project_id, issue_id)
        assert deleted_issue is None

    def test_delete_issue_not_found(self):
        """DELETE /issues/{project_id}/{issue_id} (存在しないID) のテスト"""
        project_id = "test-project-not-exist-delete"
        issue_id = "non-existent-issue-delete"
        
        response = self.client.delete(f"/issues/{project_id}/{issue_id}")
        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        
        assert "detail" in data
        assert f"Issue with ID '{issue_id}' not found in project '{project_id}'" in data["detail"]

    def test_delete_issue_failure(self):
        """DELETE /issues/{project_id}/{issue_id} (リポジトリ失敗時) のテスト"""
        # 事前にIssueを作成
        project_id = "test-project-7"
        title = "Test Issue for Delete Failure"
        
        issue = self._create_issue_in_repo(title=title, project_id=project_id)
        issue_id = issue.issue_id
        
        # deleteが例外を発生させるモックを作成
        mock_repo = MagicMock(spec=IssueRepository)
        # get_by_idは成功するがdeleteで失敗するようにする
        mock_repo.get_by_id.return_value = issue.to_dict()
        mock_repo.delete.side_effect = Exception("Database error deleting issue")
        
        # Issueモデルにモックリポジトリを設定
        Issue.set_repository(mock_repo)
        
        response = self.client.delete(f"/issues/{project_id}/{issue_id}")
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        data = response.json()
        
        assert "detail" in data
        assert "Failed to delete issue: Database error deleting issue" in data["detail"]
        
        # 元のリポジトリに戻す
        Issue.set_repository(self.fake_repo)
