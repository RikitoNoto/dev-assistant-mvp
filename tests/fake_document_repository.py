from typing import Optional, Dict, Any, List

from src.repositories.documents import DocumentRepository

class FakeDocumentRepository(DocumentRepository):
    """インメモリでドキュメントを管理するFakeリポジトリクラス"""

    def __init__(self):
        self._documents: Dict[str, Dict[str, Any]] = {}

    def initialize(self, *args, **kwargs):
        """リポジトリを初期化する（抽象メソッドの実装）"""
        pass

    def save_or_update(self, document_data: Dict[str, Any]) -> str:
        """ドキュメントを保存または更新する"""
        if not isinstance(document_data, dict):
            raise TypeError("document_data must be a dictionary")
        if "project_id" not in document_data:
            raise ValueError("project_id is required")
        
        project_id = document_data["project_id"]
        
        # 辞書のコピーを作成して保存
        self._documents[project_id] = document_data.copy()
        return project_id

    def get_by_id(self, project_id: str) -> Optional[Dict[str, Any]]:
        """IDでドキュメントを取得する"""
        return self._documents.get(project_id)

    def clear(self):
        """テスト用にリポジトリをクリアする"""
        self._documents = {}
