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
    from src.routers.issues import get_github_repository
else:
    from api import app
    from models.project import Project
    from repositories.issues.github import GitHubIssuesRepository
    from routers.issues import get_github_repository

client = TestClient(app)

class TestDeleteGitHubIssue:
    """GitHub Issue削除機能のテストクラス"""

    def test_delete_github_issue_success(self):
        """
        正常にGitHub Issueを削除できることをテスト
        """
        # テスト用のプロジェクトID
        project_id = "test-project-1"
        github_project_id = "github-project-1"
        issue_id = "issue-123"
        
        # GitHubIssuesRepositoryのモックを作成
        mock_github_repo = MagicMock(spec=GitHubIssuesRepository)
        mock_github_repo.delete_issue.return_value = True
        
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
                    response = client.delete(f"/issues/{project_id}/github/{issue_id}")
                    
                    # レスポンスを検証
                    assert response.status_code == status.HTTP_204_NO_CONTENT
                    assert response.content == b''
                    
                    # モックが正しく呼び出されたことを確認
                    mock_github_repo.delete_issue.assert_called_once_with(issue_id=issue_id)

    def test_delete_github_issue_project_not_found(self):
        """
        存在しないプロジェクトIDを指定した場合、404エラーが返されることをテスト
        """
        # テスト用のプロジェクトID
        project_id = "non-existent-project"
        issue_id = "issue-123"
        
        # Project.find_by_idをパッチして、Noneを返すようにする（プロジェクトが見つからない）
        with patch('models.project.Project.find_by_id', return_value=None):
            # APIエンドポイントを呼び出す
            response = client.delete(f"/issues/{project_id}/github/{issue_id}")
            
            # レスポンスを検証
            assert response.status_code == status.HTTP_404_NOT_FOUND
            data = response.json()
            assert "detail" in data
            assert f"Project with ID '{project_id}' not found." in data["detail"]

    def test_delete_github_issue_no_github_project_id(self):
        """
        GitHubプロジェクトIDが設定されていないプロジェクトの場合、400エラーが返されることをテスト
        """
        # テスト用のプロジェクトID
        project_id = "test-project-no-github"
        issue_id = "issue-123"
        
        # Projectモデルのモックを作成（GitHubプロジェクトIDが設定されていない）
        mock_project = MagicMock(spec=Project)
        mock_project.github_project_id = None
        
        # Project.find_by_idをパッチして、モックプロジェクトを返すようにする
        with patch('models.project.Project.find_by_id', return_value=mock_project):
            # APIエンドポイントを呼び出す
            response = client.delete(f"/issues/{project_id}/github/{issue_id}")
            
            # レスポンスを検証
            assert response.status_code == status.HTTP_400_BAD_REQUEST
            data = response.json()
            assert "detail" in data
            assert f"Project with ID '{project_id}' is not linked to a GitHub project." in data["detail"]

    def test_delete_github_issue_not_found(self):
        """
        存在しないIssue IDを指定した場合、404エラーが返されることをテスト
        """
        # テスト用のプロジェクトID
        project_id = "test-project-1"
        github_project_id = "github-project-1"
        issue_id = "non-existent-issue"
        
        # GitHubIssuesRepositoryのモックを作成（削除に失敗する）
        mock_github_repo = MagicMock(spec=GitHubIssuesRepository)
        mock_github_repo.delete_issue.return_value = False
        
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
                    response = client.delete(f"/issues/{project_id}/github/{issue_id}")
                    
                    # レスポンスを検証
                    assert response.status_code == status.HTTP_404_NOT_FOUND
                    data = response.json()
                    assert "detail" in data
                    assert f"GitHub Issue with ID '{issue_id}' not found or could not be deleted." in data["detail"]

    def test_delete_github_issue_api_error(self):
        """
        GitHub API呼び出し時に例外が発生した場合、500エラーが返されることをテスト
        """
        # テスト用のプロジェクトID
        project_id = "test-project-1"
        github_project_id = "github-project-1"
        issue_id = "issue-123"
        
        # GitHubIssuesRepositoryのモックを作成（例外を発生させる）
        mock_github_repo = MagicMock(spec=GitHubIssuesRepository)
        mock_github_repo.delete_issue.side_effect = Exception("GitHub API error")
        
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
                    response = client.delete(f"/issues/{project_id}/github/{issue_id}")
                    
                    # レスポンスを検証
                    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
                    data = response.json()
                    assert "detail" in data
                    assert "Failed to delete GitHub issue: GitHub API error" in data["detail"]
