from __future__ import annotations
from datetime import datetime
from typing import Optional, ClassVar, Self, Dict, Any
from pydantic import BaseModel
from repositories.documents import DocumentRepository
from routers.utils import (
    get_plan_document_repository,
    get_tech_spec_document_repository,
)


class Document(BaseModel):
    """
    企画ドキュメントを表すデータモデル。
    リポジトリを利用して永続化機能を持ちます。
    """
    # クラス変数としてリポジトリを保持（依存性注入用）
    _repository: ClassVar[Optional[DocumentRepository]] = None

    def __init__(self, **data):
        if "document_id" not in data and "project_id" in data:
            data["document_id"] = data["project_id"]
        if "created_at" not in data:
            data["created_at"] = datetime.now()
        if "updated_at" not in data:
            data["updated_at"] = datetime.now()
        super().__init__(**data)

    project_id: str
    document_id: str
    content: str
    created_at: datetime
    updated_at: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """
        モデルを辞書に変換します
        
        Returns:
            Dict[str, Any]: モデルの辞書表現
        """
        return {
            "project_id": self.project_id,
            "document_id": self.document_id,
            "content": self.content,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Self:
        """
        辞書からモデルを作成します
        
        Args:
            data: モデルデータを含む辞書
            
        Returns:
            Self: 作成されたモデルインスタンス
        """
        # ISO形式の日付文字列をdatetimeオブジェクトに変換
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        
        updated_at = data.get("updated_at")
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at)
        
        return cls(
            project_id=data["project_id"],
            document_id=data["document_id"],
            content=data["content"],
            created_at=created_at,
            updated_at=updated_at
        )
    
    @classmethod
    def set_repository(cls, repository: DocumentRepository) -> None:
        """
        リポジトリを設定します。依存性注入のために使用します。
        
        Args:
            repository: 使用するDocumentRepositoryの実装
        """
        cls._repository = repository
    
    @classmethod
    def get_repository(cls) -> DocumentRepository:
        """
        現在のリポジトリを取得します。設定されていない場合はデフォルトのリポジトリを使用します。
        
        Returns:
            DocumentRepository: 使用するリポジトリ
        """
        if cls._repository is None:
            cls._repository = get_plan_document_repository()
        return cls._repository
    
    def create(self) -> Self:
        """
        新しいドキュメントを作成します。
        
        Returns:
            Self: 作成されたドキュメントのインスタンス
        """
        self.get_repository().save_or_update(self.to_dict())
        return self
    
    def save(self) -> Self:
        """
        ドキュメントを永続化します。
        
        Returns:
            Self: 保存されたドキュメントのインスタンス
        """
        self.get_repository().save_or_update(self.to_dict())
        return self
    
    def update(self, **kwargs) -> Self:
        """
        ドキュメントを更新します。
        
        Returns:
            Self: 更新されたドキュメントのインスタンス
        """
        self.updated_at = datetime.now()
        for key, value in kwargs.items():
            setattr(self, key, value)
        return self.save()
    
    @classmethod
    def find_by_id(cls, project_id: str) -> Optional["Document"]:
        """
        IDによってドキュメントを検索します。
        
        Args:
            project_id: 検索するドキュメントのID
            
        Returns:
            Optional[Self]: 見つかったドキュメント、または見つからない場合はNone
        """
        data = cls.get_repository().get_by_id(project_id)
        return cls.from_dict(data) if data else None

class PlanDocument(Document):
    """
    企画ドキュメントを表すデータモデル。
    リポジトリを利用して永続化機能を持ちます。
    """
    # クラス変数としてリポジトリを保持（依存性注入用）
    _repository: ClassVar[Optional[DocumentRepository]] = None
    
    def __init__(self, **data):
        if "document_id" not in data and "project_id" in data:
            data["document_id"] = data["project_id"]
        if "created_at" not in data:
            data["created_at"] = datetime.now()
        if "updated_at" not in data:
            data["updated_at"] = datetime.now()
        super().__init__(**data)
    
    @classmethod
    def get_repository(cls) -> DocumentRepository:
        """
        現在のリポジトリを取得します。設定されていない場合はデフォルトのリポジトリを使用します。
        
        Returns:
            DocumentRepository: 使用するリポジトリ
        """
        if cls._repository is None:
            cls._repository = get_plan_document_repository()
        return cls._repository
    
class TechSpecDocument(Document):
    """
    技術仕様ドキュメントを表すデータモデル。
    リポジトリを利用して永続化機能を持ちます。
    """
    # クラス変数としてリポジトリを保持（依存性注入用）
    _repository: ClassVar[Optional[DocumentRepository]] = None
    
    def __init__(self, **data):
        if "document_id" not in data and "project_id" in data:
            data["document_id"] = data["project_id"]
        if "created_at" not in data:
            data["created_at"] = datetime.now()
        if "updated_at" not in data:
            data["updated_at"] = datetime.now()
        super().__init__(**data)
    
    @classmethod
    def get_repository(cls) -> DocumentRepository:
        """
        現在のリポジトリを取得します。設定されていない場合はデフォルトのリポジトリを使用します。
        
        Returns:
            DocumentRepository: 使用するリポジトリ
        """
        if cls._repository is None:
            cls._repository = get_tech_spec_document_repository()
        return cls._repository
    