from datetime import datetime
from unittest.mock import patch, MagicMock
from tests.fake_document_repository import FakeDocumentRepository
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.models.document import Document
    from src.repositories.documents import DocumentRepository
else:
    from models.document import Document
    from repositories.documents import DocumentRepository


class TestDocument:
    """Document モデルのテストクラス"""

    def setup_method(self):
        """各テストメソッドの前に実行されるセットアップ"""
        # テスト用のFakeリポジトリを作成
        self.fake_repository = FakeDocumentRepository()
        # Document クラスにFakeリポジトリを設定
        Document.set_repository(self.fake_repository)

    def teardown_method(self):
        """各テストメソッドの後に実行されるクリーンアップ"""
        # テスト間の独立性を保つためにリポジトリをリセット
        Document._repository = None
        # リポジトリ内のデータをクリア
        self.fake_repository.clear()

    def test_set_and_get_repository(self):
        """リポジトリの設定と取得のテスト"""
        # リポジトリをリセット
        Document._repository = None
        
        # カスタムリポジトリを設定
        custom_repo = FakeDocumentRepository()
        Document.set_repository(custom_repo)
        
        # 取得したリポジトリが設定したものと同じであることを確認
        assert Document.get_repository() is custom_repo

    def test_get_repository_default(self):
        """デフォルトリポジトリの取得テスト"""
        # リポジトリをリセット
        Document._repository = None
        
        # get_plan_document_repository をモック化
        with patch('models.document.get_plan_document_repository') as mock_get_repo:
            default_repo = MagicMock(spec=DocumentRepository)
            mock_get_repo.return_value = default_repo
            
            # リポジトリが設定されていない場合、デフォルトリポジトリが取得されることを確認
            assert Document.get_repository() is default_repo
            mock_get_repo.assert_called_once()

    def test_create_adds_document_to_repository(self):
        """create メソッドがリポジトリにドキュメントを追加することをテスト"""
        # 初期状態ではリポジトリは空
        assert self.fake_repository.get_by_id("test-project-id") is None
        
        # ドキュメントを作成
        document = Document(
            project_id="test-project-id",
            document_id="test-project-id",
            content="テストコンテンツ"
        )
            
        # create メソッドを呼び出し
        result = document.create()
            
        # 戻り値が正しいことを確認
        assert result is document
            
        # リポジトリにドキュメントデータが追加されたことを確認
        saved_document_data = self.fake_repository.get_by_id("test-project-id")
        assert saved_document_data is not None
        assert saved_document_data["project_id"] == "test-project-id"
        assert saved_document_data["content"] == "テストコンテンツ"

    def test_save_updates_existing_document_in_repository(self):
        """save メソッドが既存のドキュメントを更新することをテスト"""
        # ドキュメントを作成して保存
        document = Document(
            project_id="test-id",
            document_id="test-id",
            content="元のコンテンツ"
        )
        self.fake_repository.save_or_update(document.to_dict())
        
        # 同じIDで新しいドキュメントを作成して更新
        updated_document = Document(
            project_id="test-id",
            document_id="test-id",
            content="更新後のコンテンツ"
        )
        updated_document.save()
        
        # ドキュメントが更新されていることを確認
        saved_document_data = self.fake_repository.get_by_id("test-id")
        assert saved_document_data is not None
        assert saved_document_data["content"] == "更新後のコンテンツ"

    def test_update_modifies_document_properties(self):
        """update メソッドがドキュメントのプロパティを更新することをテスト"""
        # ドキュメントを作成して保存
        document = Document(
            project_id="update-test-id",
            document_id="update-test-id",
            content="元のコンテンツ"
        )
        self.fake_repository.save_or_update(document.to_dict())
        
        # update メソッドを呼び出し
        old_updated_at = document.updated_at
        document.update(content="更新されたコンテンツ")
        
        # プロパティが更新されていることを確認
        assert document.content == "更新されたコンテンツ"
        assert document.updated_at > old_updated_at
        
        # リポジトリ内のドキュメントも更新されていることを確認
        saved_document_data = self.fake_repository.get_by_id("update-test-id")
        assert saved_document_data is not None
        assert saved_document_data["content"] == "更新されたコンテンツ"

    def test_find_by_id_retrieves_document_from_repository(self):
        """find_by_id メソッドがリポジトリからドキュメントを取得することをテスト"""
        # テスト用ドキュメントをリポジトリに直接追加
        test_document = Document(
            project_id="test-id",
            document_id="test-id",
            content="検索ドキュメント",
            created_at=datetime(2023, 1, 1, 12, 0, 0),
            updated_at=datetime(2023, 1, 1, 12, 0, 0)
        )
        self.fake_repository.save_or_update(test_document.to_dict())
        
        # find_by_id メソッドを呼び出し
        result = Document.find_by_id("test-id")
        
        # 正しいドキュメントが取得できたことを確認
        assert result is not None
        assert result.project_id == "test-id"
        assert result.document_id == "test-id"
        assert result.content == "検索ドキュメント"
        assert isinstance(result.created_at, datetime)

    def test_find_by_id_returns_none_for_nonexistent_document(self):
        """find_by_id メソッドが存在しないIDに対してNoneを返すことをテスト"""
        # 存在しないIDで検索
        result = Document.find_by_id("non-existent-id")
        
        # 結果がNoneであることを確認
        assert result is None

    def test_document_initialization(self):
        """ドキュメント初期化のテスト"""
        # project_idのみを指定した場合、document_idが自動設定されることを確認
        document = Document(
            project_id="auto-doc-id",
            content="コンテンツ"
        )
        assert document.document_id == "auto-doc-id"
        
        # created_atとupdated_atが自動設定されることを確認
        assert isinstance(document.created_at, datetime)
        assert isinstance(document.updated_at, datetime)
        
        # 明示的に値を指定した場合、その値が使用されることを確認
        specific_time = datetime(2023, 5, 15, 10, 0, 0)
        document_with_specific = Document(
            project_id="specific-id",
            document_id="specific-doc-id",
            content="特定の値を持つドキュメント",
            created_at=specific_time,
            updated_at=specific_time
        )
        assert document_with_specific.document_id == "specific-doc-id"
        assert document_with_specific.created_at == specific_time
        assert document_with_specific.updated_at == specific_time
        
    def test_to_dict_and_from_dict(self):
        """to_dictとfrom_dictメソッドのテスト"""
        # テスト用のドキュメントを作成
        original = Document(
            project_id="dict-test-id",
            document_id="dict-test-id",
            content="辞書変換テスト",
            created_at=datetime(2023, 5, 15, 10, 0, 0),
            updated_at=datetime(2023, 5, 15, 10, 0, 0)
        )
        
        # to_dictメソッドで辞書に変換
        doc_dict = original.to_dict()
        
        # 辞書の内容を確認
        assert doc_dict["project_id"] == "dict-test-id"
        assert doc_dict["document_id"] == "dict-test-id"
        assert doc_dict["content"] == "辞書変換テスト"
        assert doc_dict["created_at"] == "2023-05-15T10:00:00"
        assert doc_dict["updated_at"] == "2023-05-15T10:00:00"
        
        # from_dictメソッドでモデルに戻す
        restored = Document.from_dict(doc_dict)
        
        # 元のモデルと一致することを確認
        assert restored.project_id == original.project_id
        assert restored.document_id == original.document_id
        assert restored.content == original.content
        assert restored.created_at == original.created_at
        assert restored.updated_at == original.updated_at
