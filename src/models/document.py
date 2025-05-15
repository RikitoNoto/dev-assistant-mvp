from __future__ import annotations
from datetime import datetime
from typing import Optional, ClassVar, Self
from pydantic import BaseModel
from repositories.documents import DocumentRepository
from routers.utils import get_plan_document_repository


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
        self.get_repository().save_or_update(self)
        return self
    
    def save(self) -> Self:
        """
        ドキュメントを永続化します。
        
        Returns:
            Self: 保存されたドキュメントのインスタンス
        """
        self.get_repository().save_or_update(self)
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
        return cls.get_repository().get_by_id(project_id)
