import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock
import uuid

from src.models.project import Project
from src.repositories.projects import ProjectRepository
from tests.fake_project_repository import FakeProjectRepository


class TestProject:
    """Project モデルのテストクラス"""

    def setup_method(self):
        """各テストメソッドの前に実行されるセットアップ"""
        # テスト用のFakeリポジトリを作成
        self.fake_repository = FakeProjectRepository()
        # Project クラスにFakeリポジトリを設定
        Project.set_repository(self.fake_repository)

    def teardown_method(self):
        """各テストメソッドの後に実行されるクリーンアップ"""
        # テスト間の独立性を保つためにリポジトリをリセット
        Project._repository = None
        # リポジトリ内のデータをクリア
        self.fake_repository.clear()

    def test_set_and_get_repository(self):
        """リポジトリの設定と取得のテスト"""
        # リポジトリをリセット
        Project._repository = None
        
        # カスタムリポジトリを設定
        custom_repo = FakeProjectRepository()
        Project.set_repository(custom_repo)
        
        # 取得したリポジトリが設定したものと同じであることを確認
        assert Project.get_repository() is custom_repo

    def test_get_repository_default(self):
        """デフォルトリポジトリの取得テスト"""
        # リポジトリをリセット
        Project._repository = None
        
        # get_project_repository をモック化
        with patch('src.models.project.get_project_repository') as mock_get_repo:
            default_repo = MagicMock(spec=ProjectRepository)
            mock_get_repo.return_value = default_repo
            
            # リポジトリが設定されていない場合、デフォルトリポジトリが取得されることを確認
            assert Project.get_repository() is default_repo
            mock_get_repo.assert_called_once()

    def test_create_adds_project_to_repository(self):
        """create メソッドがリポジトリにプロジェクトを追加することをテスト"""
        # 初期状態ではリポジトリは空
        assert len(self.fake_repository.get_all()) == 0
        
        # UUID生成をモック化して予測可能な値にする
        with patch('src.models.project.uuid4', return_value=uuid.UUID('12345678-1234-5678-1234-567812345678')):
            project = Project(title="新規プロジェクト")
            
            # create メソッドを呼び出し
            project.create()
            
            # 戻り値が正しいことを確認
            assert project.project_id == "12345678-1234-5678-1234-567812345678"
            
            # リポジトリにプロジェクトが追加されたことを確認
            assert len(self.fake_repository.get_all()) == 1
            saved_project = self.fake_repository.get_by_id(project.project_id)
            assert saved_project is not None
            assert saved_project.title == "新規プロジェクト"

    def test_save_updates_existing_project_in_repository(self):
        """save メソッドが既存のプロジェクトを更新することをテスト"""
        # プロジェクトを作成して保存
        project = Project(project_id="test-id", title="元のタイトル")
        self.fake_repository.save_or_update(project)
        
        # 同じIDで新しいプロジェクトを作成して更新
        updated_project = Project(project_id="test-id", title="更新後のタイトル")
        updated_project.save()
        
        # リポジトリ内のプロジェクト数が変わっていないことを確認
        assert len(self.fake_repository.get_all()) == 1
        
        # プロジェクトが更新されていることを確認
        saved_project = self.fake_repository.get_by_id("test-id")
        assert saved_project is not None
        assert saved_project.title == "更新後のタイトル"

    def test_find_by_id_retrieves_project_from_repository(self):
        """find_by_id メソッドがリポジトリからプロジェクトを取得することをテスト"""
        # テスト用プロジェクトをリポジトリに直接追加
        test_project = Project(
            project_id="test-id",
            title="検索プロジェクト",
            created_at=datetime(2023, 1, 1, 12, 0, 0),
            updated_at=datetime(2023, 1, 1, 12, 0, 0)
        )
        self.fake_repository.save_or_update(test_project)
        
        # find_by_id メソッドを呼び出し
        result = Project.find_by_id("test-id")
        
        # 正しいプロジェクトが取得できたことを確認
        assert result is not None
        assert result.project_id == "test-id"
        assert result.title == "検索プロジェクト"
        assert result.created_at == datetime(2023, 1, 1, 12, 0, 0)

    def test_find_by_id_returns_none_for_nonexistent_project(self):
        """find_by_id メソッドが存在しないIDに対してNoneを返すことをテスト"""
        # リポジトリが空であることを確認
        assert len(self.fake_repository.get_all()) == 0
        
        # 存在しないIDで検索
        result = Project.find_by_id("non-existent-id")
        
        # 結果がNoneであることを確認
        assert result is None

    def test_find_all_retrieves_all_projects_from_repository(self):
        """find_all メソッドがリポジトリからすべてのプロジェクトを取得することをテスト"""
        # 初期状態ではリポジトリは空
        assert len(self.fake_repository.get_all()) == 0
        
        # 複数のプロジェクトをリポジトリに追加
        project1 = Project(project_id="id-1", title="プロジェクト1")
        project2 = Project(project_id="id-2", title="プロジェクト2")
        project3 = Project(project_id="id-3", title="プロジェクト3")
        
        self.fake_repository.save_or_update(project1)
        self.fake_repository.save_or_update(project2)
        self.fake_repository.save_or_update(project3)
        
        # find_all メソッドを呼び出し
        results = Project.find_all()
        
        # 正しい数のプロジェクトが取得できたことを確認
        assert len(results) == 3
        
        # 各プロジェクトが含まれていることを確認
        project_ids = [p.project_id for p in results]
        assert "id-1" in project_ids
        assert "id-2" in project_ids
        assert "id-3" in project_ids

    def test_delete_removes_project_from_repository(self):
        """delete メソッドがリポジトリからプロジェクトを削除することをテスト"""
        # プロジェクトを作成して保存
        project = Project(project_id="delete-id", title="削除プロジェクト")
        self.fake_repository.save_or_update(project)
        
        # 保存されていることを確認
        assert len(self.fake_repository.get_all()) == 1
        
        # delete メソッドを呼び出し
        result = project.delete()
        
        # 削除が成功したことを確認
        assert result is True
        
        # リポジトリからプロジェクトが削除されたことを確認
        assert len(self.fake_repository.get_all()) == 0
        assert self.fake_repository.get_by_id("delete-id") is None

    def test_delete_not_found(self):
        """存在しないプロジェクト削除メソッドのテスト"""
        project = Project(project_id="non-existent-id", title="存在しないプロジェクト")
        
        # delete メソッドを呼び出し、例外が発生することを確認
        with pytest.raises(ValueError):
            project.delete()
