from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel
from routers.utils import get_project_repository
from repositories.projects import ProjectRepository
from typing import Optional, ClassVar, Self
from uuid import uuid4



class Project(BaseModel):
    """
    プロジェクトを表すデータモデル。
    リポジトリを利用して永続化機能を持ちます。
    """
    # クラス変数としてリポジトリを保持（依存性注入用）
    _repository: ClassVar[Optional[ProjectRepository]] = None

    def __init__(self, **data):
        if "project_id" not in data:
            data["project_id"] = str(uuid4())
        if "created_at" not in data:
            data["created_at"] = datetime.now()
        if "updated_at" not in data:
            data["updated_at"] = datetime.now()
        super().__init__(**data)

    project_id: str
    title: str
    created_at: datetime
    updated_at: datetime
    
    @classmethod
    def set_repository(cls, repository: ProjectRepository) -> None:
        """
        リポジトリを設定します。依存性注入のために使用します。
        
        Args:
            repository: 使用するProjectRepositoryの実装
        """
        cls._repository = repository
    
    @classmethod
    def get_repository(cls) -> ProjectRepository:
        """
        現在のリポジトリを取得します。設定されていない場合はデフォルトのリポジトリを使用します。
        
        Returns:
            ProjectRepository: 使用するリポジトリ
        """
        if cls._repository is None:
            cls._repository = get_project_repository()
        return cls._repository
    
    def create(self) -> str:
        """
        新しいプロジェクトを作成します。
        
        Args:
            title: プロジェクトのタイトル
            
        Returns:
            作成されたプロジェクトのインスタンス
        """
        return self.get_repository().save_or_update(self)
    
    def save(self) -> str:
        """
        プロジェクトを永続化します。
        
        Returns:
            str: 保存されたプロジェクトのID
        """
        return self.get_repository().save_or_update(self)
    
    @classmethod
    def find_by_id(cls, project_id: str) -> Optional[Self]:
        """
        IDによってプロジェクトを検索します。
        
        Args:
            project_id: 検索するプロジェクトのID
            
        Returns:
            Optional[Self]: 見つかったプロジェクト、または見つからない場合はNone
        """
        return cls.get_repository().get_by_id(project_id)
    
    @classmethod
    def find_all(cls) -> list[Self]:
        """
        すべてのプロジェクトを取得します。
        
        Returns:
            list[Self]: プロジェクトのリスト
        """
        return cls.get_repository().get_all()
    
    def delete(self) -> bool:
        """
        プロジェクトを削除します。
        
        Returns:
            bool: 削除が成功した場合はTrue
        """
        return self.get_repository().delete_by_id(self.project_id)
    