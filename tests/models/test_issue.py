import uuid
import pytest
from datetime import datetime
from tests.test_issues import FakeIssueRepository
from typing import TYPE_CHECKING
from unittest.mock import patch, MagicMock

if TYPE_CHECKING:
    from src.models.issue import Issue
    from src.repositories.issues import IssueRepository
else:
    from models.issue import Issue
    from repositories.issues import IssueRepository


class TestIssue:
    """Issue モデルのテストクラス"""

    def setup_method(self):
        """各テストメソッドの前に実行されるセットアップ"""
        # テスト用のFakeリポジトリを作成
        self.fake_repository = FakeIssueRepository()
        # Issue クラスにFakeリポジトリを設定
        Issue.set_repository(self.fake_repository)

    def teardown_method(self):
        """各テストメソッドの後に実行されるクリーンアップ"""
        # テスト間の独立性を保つためにリポジトリをリセット
        Issue._repository = None
        # リポジトリ内のデータをクリア
        self.fake_repository.clear()

    def test_set_and_get_repository(self):
        """リポジトリの設定と取得のテスト"""
        # リポジトリをリセット
        Issue._repository = None
        
        # カスタムリポジトリを設定
        custom_repo = FakeIssueRepository()
        Issue.set_repository(custom_repo)
        
        # 取得したリポジトリが設定したものと同じであることを確認
        assert Issue.get_repository() is custom_repo

    def test_get_repository_default(self):
        """デフォルトリポジトリの取得テスト"""
        # リポジトリをリセット
        Issue._repository = None
        
        # get_issue_repository をモック化
        with patch('models.issue.get_issue_repository') as mock_get_repo:
            default_repo = MagicMock(spec=IssueRepository)
            mock_get_repo.return_value = default_repo
            
            # リポジトリが設定されていない場合、デフォルトリポジトリが取得されることを確認
            assert Issue.get_repository() is default_repo
            mock_get_repo.assert_called_once()

    def test_create_adds_issue_to_repository(self):
        """create メソッドがリポジトリにIssueを追加することをテスト"""
        # 初期状態ではリポジトリは空
        project_id = "test-project"
        assert len(self.fake_repository.get_by_project_id(project_id)) == 0
        
        # UUID生成をモック化して予測可能な値にする
        with patch('models.issue.uuid4', return_value=uuid.UUID('12345678-1234-5678-1234-567812345678')):
            issue = Issue(project_id=project_id, title="新規Issue")
            
            # create メソッドを呼び出し
            issue.create()
            
            # 戻り値が正しいことを確認
            assert issue.issue_id == "12345678-1234-5678-1234-567812345678"
            
            # リポジトリにIssueが追加されたことを確認
            issues = self.fake_repository.get_by_project_id(project_id)
            assert len(issues) == 1
            saved_issue_data = self.fake_repository.get_by_id(project_id, issue.issue_id)
            assert saved_issue_data is not None
            assert saved_issue_data.get('title') == "新規Issue"

    def test_save_updates_existing_issue_in_repository(self):
        """save メソッドが既存のIssueを更新することをテスト"""
        # プロジェクトIDとIssue IDを設定
        project_id = "test-project"
        issue_id = "test-issue-id"
        
        # Issueを作成して保存
        issue = Issue(project_id=project_id, issue_id=issue_id, title="元のタイトル")
        self.fake_repository.save_or_update(issue.to_dict())
        
        # 同じIDで新しいIssueを作成して更新
        updated_issue = Issue(project_id=project_id, issue_id=issue_id, title="更新後のタイトル")
        updated_issue.save()
        
        # リポジトリ内のIssue数が変わっていないことを確認
        issues = self.fake_repository.get_by_project_id(project_id)
        assert len(issues) == 1
        
        # Issueが更新されていることを確認
        saved_issue_data = self.fake_repository.get_by_id(project_id, issue_id)
        assert saved_issue_data is not None
        assert saved_issue_data['title'] == "更新後のタイトル"

    def test_update_modifies_issue_properties(self):
        """update メソッドがIssueのプロパティを更新することをテスト"""
        # Issueを作成して保存
        project_id = "test-project"
        issue_id = "test-issue-id"
        issue = Issue(
            project_id=project_id,
            issue_id=issue_id,
            title="元のタイトル",
            description="元の説明",
            status="todo"
        )
        self.fake_repository.save_or_update(issue.to_dict())
        
        # 更新前の状態を確認
        original_updated_at = issue.updated_at
        
        # update メソッドを呼び出し
        issue.update(title="更新後のタイトル", description="更新後の説明", status="in_progress")
        
        # 更新されたIssueを取得
        updated_issue_data = self.fake_repository.get_by_id(project_id, issue_id)
        
        # プロパティが更新されていることを確認
        assert updated_issue_data is not None
        assert updated_issue_data['title'] == "更新後のタイトル"
        assert updated_issue_data['description'] == "更新後の説明"
        assert updated_issue_data['status'] == "in_progress"
        # datetime文字列を比較する場合は、元の値も文字列化する
        updated_at = updated_issue_data['updated_at']
        assert (updated_at > original_updated_at.isoformat() if isinstance(updated_at, str) 
               else updated_at > original_updated_at)

    def test_find_by_id_retrieves_issue_from_repository(self):
        """find_by_id メソッドがリポジトリからIssueを取得することをテスト"""
        # テスト用Issueをリポジトリに直接追加
        project_id = "test-project"
        issue_id = "test-issue-id"
        test_issue = Issue(
            project_id=project_id,
            issue_id=issue_id,
            title="検索Issue",
            description="テスト用の説明",
            status="todo",
            created_at=datetime(2023, 1, 1, 12, 0, 0),
            updated_at=datetime(2023, 1, 1, 12, 0, 0)
        )
        self.fake_repository.save_or_update(test_issue.to_dict())
        
        # find_by_id メソッドを呼び出し
        result = Issue.find_by_id(project_id, issue_id)
        
        # 正しいIssueが取得できたことを確認
        assert result is not None
        assert result.project_id == project_id
        assert result.issue_id == issue_id
        assert result.title == "検索Issue"
        assert result.description == "テスト用の説明"
        assert result.status == "todo"
        assert result.created_at == datetime(2023, 1, 1, 12, 0, 0)

    def test_find_by_id_returns_none_for_nonexistent_issue(self):
        """find_by_id メソッドが存在しないIDに対してNoneを返すことをテスト"""
        project_id = "test-project"
        issue_id = "non-existent-id"
        
        # 存在しないIDで検索
        result = Issue.find_by_id(project_id, issue_id)
        
        # 結果がNoneであることを確認
        assert result is None

    def test_find_by_project_id_retrieves_issues_for_project(self):
        """find_by_project_id メソッドがプロジェクトに関連するすべてのIssueを取得することをテスト"""
        # プロジェクトIDを設定
        project_id = "test-project"
        
        # 初期状態ではリポジトリは空
        assert len(self.fake_repository.get_by_project_id(project_id)) == 0
        
        # 複数のIssueをリポジトリに追加
        issue1 = Issue(project_id=project_id, issue_id="id-1", title="Issue1")
        issue2 = Issue(project_id=project_id, issue_id="id-2", title="Issue2")
        issue3 = Issue(project_id=project_id, issue_id="id-3", title="Issue3")
        
        self.fake_repository.save_or_update(issue1.to_dict())
        self.fake_repository.save_or_update(issue2.to_dict())
        self.fake_repository.save_or_update(issue3.to_dict())
        
        # 別プロジェクトのIssueも追加
        other_project_id = "other-project"
        other_issue = Issue(project_id=other_project_id, issue_id="other-id", title="OtherIssue")
        self.fake_repository.save_or_update(other_issue.to_dict())
        
        # find_by_project_id メソッドを呼び出し
        results = Issue.find_by_project_id(project_id)
        
        # 正しい数のIssueが取得できたことを確認
        assert len(results) == 3
        
        # 各Issueが含まれていることを確認
        issue_ids = [i.issue_id for i in results]
        assert "id-1" in issue_ids
        assert "id-2" in issue_ids
        assert "id-3" in issue_ids
        
        # 別プロジェクトのIssueは含まれていないことを確認
        assert "other-id" not in issue_ids

    def test_delete_removes_issue_from_repository(self):
        """delete メソッドがリポジトリからIssueを削除することをテスト"""
        # Issueを作成して保存
        project_id = "test-project"
        issue_id = "delete-id"
        issue = Issue(project_id=project_id, issue_id=issue_id, title="削除Issue")
        self.fake_repository.save_or_update(issue.to_dict())
        
        # 保存されていることを確認
        assert self.fake_repository.get_by_id(project_id, issue_id) is not None
        
        # delete メソッドを呼び出し
        issue.delete()
        
        # リポジトリからIssueが削除されたことを確認
        assert self.fake_repository.get_by_id(project_id, issue_id) is None
