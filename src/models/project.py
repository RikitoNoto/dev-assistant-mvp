from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel
from routers.utils import get_project_repository
from repositories.data.projects import ProjectRepository
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
        if "last_opened_at" not in data:
            data["last_opened_at"] = datetime.now()
        super().__init__(**data)

    project_id: str
    title: str
    github_project_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    last_opened_at: datetime
    
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
    
    def to_dict(self) -> dict:
        """
        プロジェクトをディクショナリに変換します。
        
        Returns:
            dict: プロジェクトのデータを含むディクショナリ
        """
        return {
            "project_id": self.project_id,
            "title": self.title,
            "github_project_id": self.github_project_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_opened_at": self.last_opened_at
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> Self:
        """
        ディクショナリからプロジェクトを作成します。
        
        Args:
            data: プロジェクトデータを含むディクショナリ
            
        Returns:
            Self: 作成されたプロジェクトインスタンス
        """
        # ISO形式の日付文字列をdatetimeオブジェクトに変換
        created_at = data["created_at"]
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
            
        updated_at = data["updated_at"]
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at)
            
        last_opened_at = data.get("last_opened_at", created_at)
        if isinstance(last_opened_at, str):
            last_opened_at = datetime.fromisoformat(last_opened_at)
            
        return cls(
            project_id=data["project_id"],
            title=data["title"],
            github_project_id=data.get("github_project_id"),
            created_at=created_at,
            updated_at=updated_at,
            last_opened_at=last_opened_at
        )
    
    def create(self) -> Self:
        """
        新しいプロジェクトを作成します。
        
        Returns:
            Self: 作成されたプロジェクトのインスタンス
        """
        self.get_repository().save_or_update(self.to_dict())
        return self
    
    def save(self) -> Self:
        """
        プロジェクトを永続化します。
        
        Returns:
            Self: 保存されたプロジェクトのインスタンス
        """
        self.get_repository().save_or_update(self.to_dict())
        return self
    
    def update(self, **kwargs) -> Self:
        """
        プロジェクトを更新します。
        
        Returns:
            Self: 更新されたプロジェクトのインスタンス
        """
        self.updated_at = datetime.now()
        for key, value in kwargs.items():
            setattr(self,key,value)
        return self.save()
    
    @classmethod
    def find_by_id(cls, project_id: str) -> Optional["Project"]:
        """
        IDによってプロジェクトを検索します。
        
        Args:
            project_id: 検索するプロジェクトのID
            
        Returns:
            Optional[Self]: 見つかったプロジェクト、または見つからない場合はNone
        """
        project_data = cls.get_repository().get_by_id(project_id)
        if project_data is None:
            return None
        return cls.from_dict(project_data)
    
    @classmethod
    def find_all(cls) -> list["Project"]:
        """
        すべてのプロジェクトを取得します。
        
        Returns:
            list[Self]: プロジェクトのリスト
        """
        projects_data = cls.get_repository().get_all()
        return [cls.from_dict(project_data) for project_data in projects_data]
    
    def delete(self) -> bool:
        """
        プロジェクトを削除します。
        
        Returns:
            bool: 削除が成功した場合はTrue
        """
        return self.get_repository().delete_by_id(self.project_id)
    