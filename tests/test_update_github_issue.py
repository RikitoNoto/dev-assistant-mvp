import os
import pytest
from unittest.mock import patch, MagicMock
from fastapi import status
from fastapi.testclient import TestClient
from datetime import datetime
from typing import List, Dict, Optional, TYPE_CHECKING

# Import the app and the necessary components
if TYPE_CHECKING:
    from src.api import app
    from src.models.project import Project
    from src.repositories.issues.github import GitHubIssuesRepository
    from src.repositories.issues.issues_repository import IssueData
    from src.routers.issues import get_github_repository, GitHubIssueResponse, GitHubIssueUpdate
else:
    from api import app
    from models.project import Project
    from repositories.issues.github import GitHubIssuesRepository
    from repositories.issues.issues_repository import IssueData
    from routers.issues import get_github_repository, GitHubIssueUpdate

client = TestClient(app)

class TestUpdateGitHubIssue:
    """GitHub Issue更新機能のテストクラス"""

    def test_update_github_issue_success(self):
        """
        正常にGitHub Issueを更新できることをテスト
        """
        # テスト用のプロジェクトID
        project_id = "test-project-1"
        github_project_id = "github-project-1"
        issue_id = "issue-123"
        
        # 更新されるIssueのモックデータ
        mock_issue = IssueData(
            id=issue_id,
            title="Updated Issue Title",
            description="Updated issue description",
            url="https://github.com/test-owner/test-repo/issues/1",
            status="CLOSED",
            created_at=datetime.now(),
            updated_at=datetime.now(),
            labels=["bug", "enhancement"],
            project_status="In Progress"
        )
        
        # GitHubIssuesRepositoryのモックを作成
        mock_github_repo = MagicMock(spec=GitHubIssuesRepository)
        mock_github_repo.update_issue.return_value = mock_issue
        
        # Projectモデルのモックを作成
        mock_project = MagicMock(spec=Project)
        mock_project.github_project_id = github_project_id
        
        # リクエストデータ
        issue_data = {
            "title": "Updated Issue Title",
            "description": "Updated issue description",
            "status": "CLOSED",
            "project_status": "In Progress"
        }
        
        # 環境変数をモックして、GITHUB_TOKENが設定されているようにする
        with patch.dict(os.environ, {"GITHUB_TOKEN": "dummy_token"}):
            # get_github_repository関数をパッチして、モックリポジトリを返すようにする
            with patch('routers.issues.get_github_repository', return_value=mock_github_repo):
                # Project.find_by_idをパッチして、モックプロジェクトを返すようにする
                with patch('models.project.Project.find_by_id', return_value=mock_project):
                    # APIエンドポイントを呼び出す
                    response = client.put(f"/issues/{project_id}/github/{issue_id}", json=issue_data)
                    
                    # レスポンスを検証
                    assert response.status_code == status.HTTP_200_OK
                    data = response.json()
                    
                    # 返されたデータが期待通りであることを確認
                    assert data["id"] == issue_id
                    assert data["title"] == "Updated Issue Title"
                    assert data["description"] == "Updated issue description"
                    assert data["status"] == "CLOSED"
                    assert data["url"] == "https://github.com/test-owner/test-repo/issues/1"
                    assert "created_at" in data
                    assert "updated_at" in data
                    assert len(data["labels"]) == 2
                    assert "bug" in data["labels"]
                    assert "enhancement" in data["labels"]
                    assert data["project_status"] == "In Progress"
                    
                    # モックが正しく呼び出されたことを確認
                    mock_github_repo.update_issue.assert_called_once_with(
                        issue_id=issue_id,
                        title="Updated Issue Title",
                        description="Updated issue description",
                        status="CLOSED",
                        project_status="In Progress"
                    )

    def test_update_github_issue_partial_update(self):
        """
        一部のフィールドのみを更新できることをテスト
        """
        # テスト用のプロジェクトID
        project_id = "test-project-1"
        github_project_id = "github-project-1"
        issue_id = "issue-123"
        
        # 更新されるIssueのモックデータ
        mock_issue = IssueData(
            id=issue_id,
            title="Original Title",
            description="Updated description only",
            url="https://github.com/test-owner/test-repo/issues/1",
            status="OPEN",
            created_at=datetime.now(),
            updated_at=datetime.now(),
            labels=["bug"],
            project_status=None
        )
        
        # GitHubIssuesRepositoryのモックを作成
        mock_github_repo = MagicMock(spec=GitHubIssuesRepository)
        mock_github_repo.update_issue.return_value = mock_issue
        
        # Projectモデルのモックを作成
        mock_project = MagicMock(spec=Project)
        mock_project.github_project_id = github_project_id
        
        # リクエストデータ（説明のみ更新）
        issue_data = {
            "description": "Updated description only"
        }
        
        # 環境変数をモックして、GITHUB_TOKENが設定されているようにする
        with patch.dict(os.environ, {"GITHUB_TOKEN": "dummy_token"}):
            # get_github_repository関数をパッチして、モックリポジトリを返すようにする
            with patch('routers.issues.get_github_repository', return_value=mock_github_repo):
                # Project.find_by_idをパッチして、モックプロジェクトを返すようにする
                with patch('models.project.Project.find_by_id', return_value=mock_project):
                    # APIエンドポイントを呼び出す
                    response = client.put(f"/issues/{project_id}/github/{issue_id}", json=issue_data)
                    
                    # レスポンスを検証
                    assert response.status_code == status.HTTP_200_OK
                    data = response.json()
                    
                    # 返されたデータが期待通りであることを確認
                    assert data["id"] == issue_id
                    assert data["title"] == "Original Title"
                    assert data["description"] == "Updated description only"
                    assert data["status"] == "OPEN"
                    
                    # モックが正しく呼び出されたことを確認
                    mock_github_repo.update_issue.assert_called_once_with(
                        issue_id=issue_id,
                        title=None,
                        description="Updated description only",
                        status=None,
                        project_status=None
                    )

    def test_update_github_issue_project_not_found(self):
        """
        存在しないプロジェクトIDを指定した場合、404エラーが返されることをテスト
        """
        # テスト用のプロジェクトID
        project_id = "non-existent-project"
        issue_id = "issue-123"
        
        # リクエストデータ
        issue_data = {
            "title": "Updated Title",
            "description": "Updated description"
        }
        
        # Project.find_by_idをパッチして、Noneを返すようにする（プロジェクトが見つからない）
        with patch('models.project.Project.find_by_id', return_value=None):
            # APIエンドポイントを呼び出す
            response = client.put(f"/issues/{project_id}/github/{issue_id}", json=issue_data)
            
            # レスポンスを検証
            assert response.status_code == status.HTTP_404_NOT_FOUND
            data = response.json()
            assert "detail" in data
            assert f"Project with ID '{project_id}' not found." in data["detail"]

    def test_update_github_issue_no_github_project_id(self):
        """
        GitHubプロジェクトIDが設定されていないプロジェクトの場合、400エラーが返されることをテスト
        """
        # テスト用のプロジェクトID
        project_id = "test-project-no-github"
        issue_id = "issue-123"
        
        # リクエストデータ
        issue_data = {
            "title": "Updated Title",
            "description": "Updated description"
        }
        
        # Projectモデルのモックを作成（GitHubプロジェクトIDが設定されていない）
        mock_project = MagicMock(spec=Project)
        mock_project.github_project_id = None
        
        # Project.find_by_idをパッチして、モックプロジェクトを返すようにする
        with patch('models.project.Project.find_by_id', return_value=mock_project):
            # APIエンドポイントを呼び出す
            response = client.put(f"/issues/{project_id}/github/{issue_id}", json=issue_data)
            
            # レスポンスを検証
            assert response.status_code == status.HTTP_400_BAD_REQUEST
            data = response.json()
            assert "detail" in data
            assert f"Project with ID '{project_id}' is not linked to a GitHub project." in data["detail"]

    def test_update_github_issue_not_found(self):
        """
        存在しないIssue IDを指定した場合、404エラーが返されることをテスト
        """
        # テスト用のプロジェクトID
        project_id = "test-project-1"
        github_project_id = "github-project-1"
        issue_id = "non-existent-issue"
        
        # リクエストデータ
        issue_data = {
            "title": "Updated Title",
            "description": "Updated description"
        }
        
        # GitHubIssuesRepositoryのモックを作成（更新に失敗する）
        mock_github_repo = MagicMock(spec=GitHubIssuesRepository)
        mock_github_repo.update_issue.return_value = None
        
        # Projectモデルのモックを作成
        mock_project = MagicMock(spec=Project)
        mock_project.github_project_id = github_project_id
        
        # 環境変数をモックして、GITHUB_TOKENが設定されているようにする
        with patch.dict(os.environ, {"GITHUB_TOKEN": "dummy_token"}):
            # get_github_repository関数をパッチして、モックリポジトリを返すようにする
            with patch('routers.issues.get_github_repository', return_value=mock_github_repo):
                # Project.find_by_idをパッチして、モックプロジェクトを返すようにする
                with patch('models.project.Project.find_by_id', return_value=mock_project):
                    # APIエンドポイントを呼び出す
                    response = client.put(f"/issues/{project_id}/github/{issue_id}", json=issue_data)
                    
                    # レスポンスを検証
                    assert response.status_code == status.HTTP_404_NOT_FOUND
                    data = response.json()
                    assert "detail" in data
                    assert f"GitHub Issue with ID '{issue_id}' not found or could not be updated." in data["detail"]

    def test_update_github_issue_invalid_status(self):
        """
        無効なステータスを指定した場合、400エラーが返されることをテスト
        """
        # テスト用のプロジェクトID
        project_id = "test-project-1"
        github_project_id = "github-project-1"
        issue_id = "issue-123"
        
        # リクエストデータ（無効なステータス）
        issue_data = {
            "status": "INVALID_STATUS"
        }
        
        # GitHubIssuesRepositoryのモックを作成（ValueErrorを発生させる）
        mock_github_repo = MagicMock(spec=GitHubIssuesRepository)
        mock_github_repo.update_issue.side_effect = ValueError("Invalid status: INVALID_STATUS. Status must be 'OPEN' or 'CLOSED'.")
        
        # Projectモデルのモックを作成
        mock_project = MagicMock(spec=Project)
        mock_project.github_project_id = github_project_id
        
        # 環境変数をモックして、GITHUB_TOKENが設定されているようにする
        with patch.dict(os.environ, {"GITHUB_TOKEN": "dummy_token"}):
            # get_github_repository関数をパッチして、モックリポジトリを返すようにする
            with patch('routers.issues.get_github_repository', return_value=mock_github_repo):
                # Project.find_by_idをパッチして、モックプロジェクトを返すようにする
                with patch('models.project.Project.find_by_id', return_value=mock_project):
                    # APIエンドポイントを呼び出す
                    response = client.put(f"/issues/{project_id}/github/{issue_id}", json=issue_data)
                    
                    # レスポンスを検証
                    assert response.status_code == status.HTTP_400_BAD_REQUEST
                    data = response.json()
                    assert "detail" in data
                    assert "Invalid status: INVALID_STATUS. Status must be 'OPEN' or 'CLOSED'." in data["detail"]

    def test_update_github_issue_api_error(self):
        """
        GitHub API呼び出し時に例外が発生した場合、500エラーが返されることをテスト
        """
        # テスト用のプロジェクトID
        project_id = "test-project-1"
        github_project_id = "github-project-1"
        issue_id = "issue-123"
        
        # リクエストデータ
        issue_data = {
            "title": "Updated Title",
            "description": "Updated description"
        }
        
        # GitHubIssuesRepositoryのモックを作成（例外を発生させる）
        mock_github_repo = MagicMock(spec=GitHubIssuesRepository)
        mock_github_repo.update_issue.side_effect = Exception("GitHub API error")
        
        # Projectモデルのモックを作成
        mock_project = MagicMock(spec=Project)
        mock_project.github_project_id = github_project_id
        
        # 環境変数をモックして、GITHUB_TOKENが設定されているようにする
        with patch.dict(os.environ, {"GITHUB_TOKEN": "dummy_token"}):
            # get_github_repository関数をパッチして、モックリポジトリを返すようにする
            with patch('routers.issues.get_github_repository', return_value=mock_github_repo):
                # Project.find_by_idをパッチして、モックプロジェクトを返すようにする
                with patch('models.project.Project.find_by_id', return_value=mock_project):
                    # APIエンドポイントを呼び出す
                    response = client.put(f"/issues/{project_id}/github/{issue_id}", json=issue_data)
                    
                    # レスポンスを検証
                    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
                    data = response.json()
                    assert "detail" in data
                    assert "Failed to update GitHub issue: GitHub API error" in data["detail"]
