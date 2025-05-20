import os
import pytest
from unittest.mock import patch, MagicMock
from fastapi import status
from fastapi.testclient import TestClient
from typing import List, Dict, TYPE_CHECKING

# Import the app and the necessary components
if TYPE_CHECKING:
    from src.api import app
    from src.routers.projects import get_github_repository, GitHubProject
    from src.repositories.issues.github import GitHubIssuesRepository
else:
    from api import app
    from routers.projects import get_github_repository
    from repositories.issues.github import GitHubIssuesRepository

client = TestClient(app)

class TestGitHubProjects:
    """GitHub プロジェクト関連機能のテストクラス"""

    def test_get_github_projects_success(self):
        """
        /github/projects エンドポイントが正常に GitHub プロジェクトを取得できることをテスト
        """
        # テスト用のプロジェクトデータ
        mock_projects = [
            {"id": "project1", "name": "Test Project 1"},
            {"id": "project2", "name": "Test Project 2"}
        ]
        
        # GitHubIssuesRepository のモックを作成
        mock_github_repo = MagicMock(spec=GitHubIssuesRepository)
        mock_github_repo.fetch_projects.return_value = mock_projects
        
        # 環境変数をモックして、GITHUB_TOKEN が設定されているようにする
        with patch.dict(os.environ, {"GITHUB_TOKEN": "dummy_token"}):
            # get_github_repository 関数をパッチして、モックリポジトリを返すようにする
            with patch('routers.projects.get_github_repository', return_value=mock_github_repo):
                # API エンドポイントを呼び出す
                response = client.get("/projects/github/projects")
                
                # レスポンスを検証
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert isinstance(data, list)
                assert len(data) == 2
                
                # 返されたデータが期待通りであることを確認
                assert data[0]["id"] == "project1"
                assert data[0]["name"] == "Test Project 1"
                assert data[1]["id"] == "project2"
                assert data[1]["name"] == "Test Project 2"
                
                # モックが正しく呼び出されたことを確認
                mock_github_repo.fetch_projects.assert_called_once()

    def test_get_github_projects_empty(self):
        """
        GitHub プロジェクトが存在しない場合、空のリストが返されることをテスト
        """
        # 空のプロジェクトリストを返すモック
        mock_github_repo = MagicMock(spec=GitHubIssuesRepository)
        mock_github_repo.fetch_projects.return_value = []
        
        # 環境変数をモックして、GITHUB_TOKEN が設定されているようにする
        with patch.dict(os.environ, {"GITHUB_TOKEN": "dummy_token"}):
            with patch('routers.projects.get_github_repository', return_value=mock_github_repo):
                response = client.get("/projects/github/projects")
                
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert isinstance(data, list)
                assert len(data) == 0
                
                mock_github_repo.fetch_projects.assert_called_once()

    def test_get_github_projects_error(self):
        """
        GitHub リポジトリでエラーが発生した場合、適切なエラーレスポンスが返されることをテスト
        """
        # エラーを発生させるモック
        mock_github_repo = MagicMock(spec=GitHubIssuesRepository)
        mock_github_repo.fetch_projects.side_effect = Exception("GitHub API error")
        
        # 環境変数をモックして、GITHUB_TOKEN が設定されているようにする
        with patch.dict(os.environ, {"GITHUB_TOKEN": "dummy_token"}):
            with patch('routers.projects.get_github_repository', return_value=mock_github_repo):
                response = client.get("/projects/github/projects")
                
                assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
                data = response.json()
                assert "detail" in data
                assert "Failed to fetch GitHub projects: GitHub API error" in data["detail"]
                
                mock_github_repo.fetch_projects.assert_called_once()

    def test_get_github_repository_no_token(self):
        """
        GitHub トークンが設定されていない場合、適切なエラーが発生することをテスト
        """
        # 環境変数をモックして、GITHUB_TOKEN が設定されていないようにする
        with patch.dict(os.environ, {"GITHUB_TOKEN": ""}, clear=True):
            # get_github_repository 関数をパッチして、実際の関数が呼ばれるようにする
            with patch('routers.projects.get_github_repository', side_effect=get_github_repository):
                response = client.get("/projects/github/projects")
            
            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            data = response.json()
            assert "detail" in data
            assert "GitHub token is not configured" in data["detail"]
