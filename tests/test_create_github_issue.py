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
    from src.routers.issues import get_github_repository, GitHubIssueResponse, GitHubIssueCreate
else:
    from api import app
    from models.project import Project
    from repositories.issues.github import GitHubIssuesRepository
    from repositories.issues.issues_repository import IssueData
    from routers.issues import get_github_repository, GitHubIssueCreate

client = TestClient(app)

class TestCreateGitHubIssue:
    """GitHub Issue作成機能のテストクラス"""

    def test_create_github_issue_success(self):
        """
        正常にGitHub Issueを作成できることをテスト
        """
        # テスト用のプロジェクトID
        project_id = "test-project-1"
        github_project_id = "github-project-1"
        
        # テスト用のリポジトリ情報
        mock_repositories = [
            {
                "owner": "test-owner",
                "name": "test-repo"
            }
        ]
        
        # 作成されるIssueのモックデータ
        mock_issue = IssueData(
            id="issue-123",
            title="Test Issue",
            description="This is a test issue",
            url="https://github.com/test-owner/test-repo/issues/1",
            status="OPEN",
            created_at=datetime.now(),
            updated_at=datetime.now(),
            labels=["bug", "enhancement"],
            project_status=None
        )
        
        # GitHubIssuesRepositoryのモックを作成
        mock_github_repo = MagicMock(spec=GitHubIssuesRepository)
        mock_github_repo.get_project_repositories.return_value = mock_repositories
        mock_github_repo.create_issue.return_value = mock_issue
        mock_github_repo.add_issue_to_project.return_value = True
        
        # Projectモデルのモックを作成
        mock_project = MagicMock(spec=Project)
        mock_project.github_project_id = github_project_id
        
        # リクエストデータ
        issue_data = {
            "title": "Test Issue",
            "description": "This is a test issue",
            "labels": ["bug", "enhancement"]
        }
        
        # 環境変数をモックして、GITHUB_TOKENが設定されているようにする
        with patch.dict(os.environ, {"GITHUB_TOKEN": "dummy_token"}):
            # get_github_repository関数をパッチして、モックリポジトリを返すようにする
            with patch('routers.issues.get_github_repository', return_value=mock_github_repo):
                # Project.find_by_idをパッチして、モックプロジェクトを返すようにする
                with patch('models.project.Project.find_by_id', return_value=mock_project):
                    # APIエンドポイントを呼び出す
                    response = client.post(f"/issues/{project_id}/github", json=issue_data)
                    
                    # レスポンスを検証
                    assert response.status_code == status.HTTP_201_CREATED
                    data = response.json()
                    
                    # 返されたデータが期待通りであることを確認
                    assert data["id"] == "issue-123"
                    assert data["title"] == "Test Issue"
                    assert data["description"] == "This is a test issue"
                    assert data["status"] == "OPEN"
                    assert data["url"] == "https://github.com/test-owner/test-repo/issues/1"
                    assert "created_at" in data
                    assert "updated_at" in data
                    assert len(data["labels"]) == 2
                    assert "bug" in data["labels"]
                    assert "enhancement" in data["labels"]
                    
                    # モックが正しく呼び出されたことを確認
                    mock_github_repo.get_project_repositories.assert_called_once_with(github_project_id)
                    mock_github_repo.create_issue.assert_called_once_with(
                        repository_owner="test-owner",
                        repository_name="test-repo",
                        title="Test Issue",
                        description="This is a test issue",
                        labels=["bug", "enhancement"]
                    )
                    mock_github_repo.add_issue_to_project.assert_called_once_with(
                        project_id=github_project_id,
                        issue_id="issue-123"
                    )

    def test_create_github_issue_project_not_found(self):
        """
        存在しないプロジェクトIDを指定した場合、404エラーが返されることをテスト
        """
        # テスト用のプロジェクトID
        project_id = "non-existent-project"
        
        # リクエストデータ
        issue_data = {
            "title": "Test Issue",
            "description": "This is a test issue",
            "labels": ["bug"]
        }
        
        # Project.find_by_idをパッチして、Noneを返すようにする（プロジェクトが見つからない）
        with patch('models.project.Project.find_by_id', return_value=None):
            # APIエンドポイントを呼び出す
            response = client.post(f"/issues/{project_id}/github", json=issue_data)
            
            # レスポンスを検証
            assert response.status_code == status.HTTP_404_NOT_FOUND
            data = response.json()
            assert "detail" in data
            assert f"Project with ID '{project_id}' not found." in data["detail"]

    def test_create_github_issue_no_github_project_id(self):
        """
        GitHubプロジェクトIDが設定されていないプロジェクトの場合、400エラーが返されることをテスト
        """
        # テスト用のプロジェクトID
        project_id = "test-project-no-github"
        
        # リクエストデータ
        issue_data = {
            "title": "Test Issue",
            "description": "This is a test issue",
            "labels": ["bug"]
        }
        
        # Projectモデルのモックを作成（GitHubプロジェクトIDが設定されていない）
        mock_project = MagicMock(spec=Project)
        mock_project.github_project_id = None
        
        # Project.find_by_idをパッチして、モックプロジェクトを返すようにする
        with patch('models.project.Project.find_by_id', return_value=mock_project):
            # APIエンドポイントを呼び出す
            response = client.post(f"/issues/{project_id}/github", json=issue_data)
            
            # レスポンスを検証
            assert response.status_code == status.HTTP_400_BAD_REQUEST
            data = response.json()
            assert "detail" in data
            assert f"Project with ID '{project_id}' is not linked to a GitHub project." in data["detail"]

    def test_create_github_issue_no_repositories(self):
        """
        プロジェクトに紐づくリポジトリが存在しない場合、400エラーが返されることをテスト
        """
        # テスト用のプロジェクトID
        project_id = "test-project-1"
        github_project_id = "github-project-1"
        
        # リクエストデータ
        issue_data = {
            "title": "Test Issue",
            "description": "This is a test issue",
            "labels": ["bug"]
        }
        
        # GitHubIssuesRepositoryのモックを作成（空のリポジトリリストを返す）
        mock_github_repo = MagicMock(spec=GitHubIssuesRepository)
        mock_github_repo.get_project_repositories.return_value = []
        
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
                    response = client.post(f"/issues/{project_id}/github", json=issue_data)
                    
                    # レスポンスを検証
                    assert response.status_code == status.HTTP_400_BAD_REQUEST
                    data = response.json()
                    assert "detail" in data
                    assert f"No repositories found for project with ID '{project_id}'." in data["detail"]

    def test_create_github_issue_creation_failure(self):
        """
        GitHub Issue作成に失敗した場合、500エラーが返されることをテスト
        """
        # テスト用のプロジェクトID
        project_id = "test-project-1"
        github_project_id = "github-project-1"
        
        # テスト用のリポジトリ情報
        mock_repositories = [
            {
                "owner": "test-owner",
                "name": "test-repo"
            }
        ]
        
        # リクエストデータ
        issue_data = {
            "title": "Test Issue",
            "description": "This is a test issue",
            "labels": ["bug"]
        }
        
        # GitHubIssuesRepositoryのモックを作成（Issue作成に失敗する）
        mock_github_repo = MagicMock(spec=GitHubIssuesRepository)
        mock_github_repo.get_project_repositories.return_value = mock_repositories
        mock_github_repo.create_issue.return_value = None
        
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
                    response = client.post(f"/issues/{project_id}/github", json=issue_data)
                    
                    # レスポンスを検証
                    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
                    data = response.json()
                    assert "detail" in data
                    assert "Failed to create GitHub issue." in data["detail"]

    def test_create_github_issue_api_error(self):
        """
        GitHub API呼び出し時に例外が発生した場合、500エラーが返されることをテスト
        """
        # テスト用のプロジェクトID
        project_id = "test-project-1"
        github_project_id = "github-project-1"
        
        # テスト用のリポジトリ情報
        mock_repositories = [
            {
                "owner": "test-owner",
                "name": "test-repo"
            }
        ]
        
        # リクエストデータ
        issue_data = {
            "title": "Test Issue",
            "description": "This is a test issue",
            "labels": ["bug"]
        }
        
        # GitHubIssuesRepositoryのモックを作成（例外を発生させる）
        mock_github_repo = MagicMock(spec=GitHubIssuesRepository)
        mock_github_repo.get_project_repositories.return_value = mock_repositories
        mock_github_repo.create_issue.side_effect = Exception("GitHub API error")
        
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
                    response = client.post(f"/issues/{project_id}/github", json=issue_data)
                    
                    # レスポンスを検証
                    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
                    data = response.json()
                    assert "detail" in data
                    assert "Failed to create GitHub issue: GitHub API error" in data["detail"]
