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
    from src.routers.issues import get_github_repository, GitHubIssueResponse
else:
    from api import app
    from models.project import Project
    from repositories.issues.github import GitHubIssuesRepository
    from repositories.issues.issues_repository import IssueData
    from routers.issues import get_github_repository

client = TestClient(app)

class TestGitHubIssues:
    """GitHub Issues 関連機能のテストクラス"""

    def test_get_github_issues_success(self):
        """
        /{project_id}/github エンドポイントが正常に GitHub Issues を取得できることをテスト
        """
        # テスト用のプロジェクトID
        project_id = "test-project-1"
        github_project_id = "github-project-1"
        
        # テスト用のIssueデータ
        mock_issues = [
            IssueData(
                id="issue1",
                title="Test Issue 1",
                description="Description for issue 1",
                url="https://github.com/owner/repo/issues/1",
                status="OPEN",
                created_at=datetime.now(),
                updated_at=datetime.now(),
                labels=["bug", "high-priority"]
            ),
            IssueData(
                id="issue2",
                title="Test Issue 2",
                description="Description for issue 2",
                url="https://github.com/owner/repo/issues/2",
                status="CLOSED",
                created_at=datetime.now(),
                updated_at=datetime.now(),
                labels=["enhancement"]
            )
        ]
        
        # GitHubIssuesRepository のモックを作成
        mock_github_repo = MagicMock(spec=GitHubIssuesRepository)
        mock_github_repo.fetch_issues.return_value = mock_issues
        
        # Project モデルのモックを作成
        mock_project = MagicMock(spec=Project)
        mock_project.github_project_id = github_project_id
        
        # 環境変数をモックして、GITHUB_TOKEN が設定されているようにする
        with patch.dict(os.environ, {"GITHUB_TOKEN": "dummy_token"}):
            # get_github_repository 関数をパッチして、モックリポジトリを返すようにする
            with patch('routers.issues.get_github_repository', return_value=mock_github_repo):
                # Project.find_by_id をパッチして、モックプロジェクトを返すようにする
                with patch('models.project.Project.find_by_id', return_value=mock_project):
                    # API エンドポイントを呼び出す
                    response = client.get(f"/issues/{project_id}/github")
                    
                    # レスポンスを検証
                    assert response.status_code == status.HTTP_200_OK
                    data = response.json()
                    assert isinstance(data, list)
                    assert len(data) == 2
                    
                    # 返されたデータが期待通りであることを確認
                    assert data[0]["id"] == "issue1"
                    assert data[0]["title"] == "Test Issue 1"
                    assert data[0]["description"] == "Description for issue 1"
                    assert data[0]["status"] == "OPEN"
                    assert len(data[0]["labels"]) == 2
                    assert "bug" in data[0]["labels"]
                    assert "high-priority" in data[0]["labels"]
                    
                    assert data[1]["id"] == "issue2"
                    assert data[1]["title"] == "Test Issue 2"
                    assert data[1]["status"] == "CLOSED"
                    assert len(data[1]["labels"]) == 1
                    assert "enhancement" in data[1]["labels"]
                    
                    # モックが正しく呼び出されたことを確認
                    mock_github_repo.fetch_issues.assert_called_once_with(
                        project_id=github_project_id,
                        state=None,
                        labels=None,
                        limit_per_repo=100
                    )

    def test_get_github_issues_with_filters(self):
        """
        フィルターを指定して GitHub Issues を取得できることをテスト
        """
        # テスト用のプロジェクトID
        project_id = "test-project-1"
        github_project_id = "github-project-1"
        
        # テスト用のIssueデータ (フィルター後の結果)
        mock_issues = [
            IssueData(
                id="issue1",
                title="Test Issue 1",
                description="Description for issue 1",
                url="https://github.com/owner/repo/issues/1",
                status="OPEN",
                created_at=datetime.now(),
                updated_at=datetime.now(),
                labels=["bug", "high-priority"]
            )
        ]
        
        # GitHubIssuesRepository のモックを作成
        mock_github_repo = MagicMock(spec=GitHubIssuesRepository)
        mock_github_repo.fetch_issues.return_value = mock_issues
        
        # Project モデルのモックを作成
        mock_project = MagicMock(spec=Project)
        mock_project.github_project_id = github_project_id
        
        # 環境変数をモックして、GITHUB_TOKEN が設定されているようにする
        with patch.dict(os.environ, {"GITHUB_TOKEN": "dummy_token"}):
            # get_github_repository 関数をパッチして、モックリポジトリを返すようにする
            with patch('routers.issues.get_github_repository', return_value=mock_github_repo):
                # Project.find_by_id をパッチして、モックプロジェクトを返すようにする
                with patch('models.project.Project.find_by_id', return_value=mock_project):
                    # フィルターを指定して API エンドポイントを呼び出す
                    response = client.get(f"/issues/{project_id}/github?state=OPEN&labels=bug,high-priority&limit_per_repo=50")
                    
                    # レスポンスを検証
                    assert response.status_code == status.HTTP_200_OK
                    data = response.json()
                    assert isinstance(data, list)
                    assert len(data) == 1
                    
                    # 返されたデータが期待通りであることを確認
                    assert data[0]["id"] == "issue1"
                    assert data[0]["title"] == "Test Issue 1"
                    assert data[0]["status"] == "OPEN"
                    
                    # モックが正しいパラメータで呼び出されたことを確認
                    mock_github_repo.fetch_issues.assert_called_once_with(
                        project_id=github_project_id,
                        state="OPEN",
                        labels=["bug", "high-priority"],
                        limit_per_repo=50
                    )

    def test_get_github_issues_project_not_found(self):
        """
        存在しないプロジェクトIDを指定した場合、404エラーが返されることをテスト
        """
        # テスト用のプロジェクトID
        project_id = "non-existent-project"
        
        # Project.find_by_id をパッチして、None を返すようにする（プロジェクトが見つからない）
        with patch('models.project.Project.find_by_id', return_value=None):
            # API エンドポイントを呼び出す
            response = client.get(f"/issues/{project_id}/github")
            
            # レスポンスを検証
            assert response.status_code == status.HTTP_404_NOT_FOUND
            data = response.json()
            assert "detail" in data
            assert f"Project with ID '{project_id}' not found." in data["detail"]

    def test_get_github_issues_no_github_project_id(self):
        """
        GitHubプロジェクトIDが設定されていないプロジェクトの場合、400エラーが返されることをテスト
        """
        # テスト用のプロジェクトID
        project_id = "test-project-no-github"
        
        # Project モデルのモックを作成（GitHub プロジェクト ID が設定されていない）
        mock_project = MagicMock(spec=Project)
        mock_project.github_project_id = None
        
        # Project.find_by_id をパッチして、モックプロジェクトを返すようにする
        with patch('models.project.Project.find_by_id', return_value=mock_project):
            # API エンドポイントを呼び出す
            response = client.get(f"/issues/{project_id}/github")
            
            # レスポンスを検証
            assert response.status_code == status.HTTP_400_BAD_REQUEST
            data = response.json()
            assert "detail" in data
            assert f"Project with ID '{project_id}' is not linked to a GitHub project." in data["detail"]

    def test_get_github_issues_no_token(self):
        """
        GitHub トークンが設定されていない場合、500エラーが返されることをテスト
        """
        # テスト用のプロジェクトID
        project_id = "test-project-1"
        
        # Project モデルのモックを作成
        mock_project = MagicMock(spec=Project)
        mock_project.github_project_id = "github-project-1"
        
        # 環境変数をモックして、GITHUB_TOKEN が設定されていないようにする
        with patch.dict(os.environ, {}, clear=True):
            # Project.find_by_id をパッチして、モックプロジェクトを返すようにする
            with patch('models.project.Project.find_by_id', return_value=mock_project):
                # get_github_repository 関数をパッチして、実際の関数が呼ばれるようにする
                with patch('routers.issues.get_github_repository', side_effect=get_github_repository):
                    # API エンドポイントを呼び出す
                    response = client.get(f"/issues/{project_id}/github")
                    
                    # レスポンスを検証
                    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
                    data = response.json()
                    assert "detail" in data
                    assert "GitHub token is not configured" in data["detail"]

    def test_get_github_issues_api_error(self):
        """
        GitHub API でエラーが発生した場合、500エラーが返されることをテスト
        """
        # テスト用のプロジェクトID
        project_id = "test-project-1"
        github_project_id = "github-project-1"
        
        # GitHubIssuesRepository のモックを作成（エラーを発生させる）
        mock_github_repo = MagicMock(spec=GitHubIssuesRepository)
        mock_github_repo.fetch_issues.side_effect = Exception("GitHub API error")
        
        # Project モデルのモックを作成
        mock_project = MagicMock(spec=Project)
        mock_project.github_project_id = github_project_id
        
        # 環境変数をモックして、GITHUB_TOKEN が設定されているようにする
        with patch.dict(os.environ, {"GITHUB_TOKEN": "dummy_token"}):
            # get_github_repository 関数をパッチして、モックリポジトリを返すようにする
            with patch('routers.issues.get_github_repository', return_value=mock_github_repo):
                # Project.find_by_id をパッチして、モックプロジェクトを返すようにする
                with patch('models.project.Project.find_by_id', return_value=mock_project):
                    # API エンドポイントを呼び出す
                    response = client.get(f"/issues/{project_id}/github")
                    
                    # レスポンスを検証
                    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
                    data = response.json()
                    assert "detail" in data
                    assert "Failed to fetch GitHub issues: GitHub API error" in data["detail"]
                    
                    # モックが正しく呼び出されたことを確認
                    mock_github_repo.fetch_issues.assert_called_once()

    def test_get_github_issues_empty_result(self):
        """
        GitHub Issues が存在しない場合、空のリストが返されることをテスト
        """
        # テスト用のプロジェクトID
        project_id = "test-project-1"
        github_project_id = "github-project-1"
        
        # GitHubIssuesRepository のモックを作成（空のリストを返す）
        mock_github_repo = MagicMock(spec=GitHubIssuesRepository)
        mock_github_repo.fetch_issues.return_value = []
        
        # Project モデルのモックを作成
        mock_project = MagicMock(spec=Project)
        mock_project.github_project_id = github_project_id
        
        # 環境変数をモックして、GITHUB_TOKEN が設定されているようにする
        with patch.dict(os.environ, {"GITHUB_TOKEN": "dummy_token"}):
            # get_github_repository 関数をパッチして、モックリポジトリを返すようにする
            with patch('routers.issues.get_github_repository', return_value=mock_github_repo):
                # Project.find_by_id をパッチして、モックプロジェクトを返すようにする
                with patch('models.project.Project.find_by_id', return_value=mock_project):
                    # API エンドポイントを呼び出す
                    response = client.get(f"/issues/{project_id}/github")
                    
                    # レスポンスを検証
                    assert response.status_code == status.HTTP_200_OK
                    data = response.json()
                    assert isinstance(data, list)
                    assert len(data) == 0
                    
                    # モックが正しく呼び出されたことを確認
                    mock_github_repo.fetch_issues.assert_called_once()
