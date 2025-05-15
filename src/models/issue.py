from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel
from routers.utils import get_issue_repository
from repositories.issues import IssueRepository
from typing import Optional, ClassVar, Self, List
from uuid import uuid4


class Issue(BaseModel):
    """
    Issueを表すデータモデル。
    リポジトリを利用して永続化機能を持ちます。
    """
    # クラス変数としてリポジトリを保持（依存性注入用）
    _repository: ClassVar[Optional[IssueRepository]] = None

    def __init__(self, **data):
        if "issue_id" not in data:
            data["issue_id"] = str(uuid4())
        if "created_at" not in data:
            data["created_at"] = datetime.now()
        if "updated_at" not in data:
            data["updated_at"] = datetime.now()
        if "description" not in data:
            data["description"] = ""
        if "status" not in data:
            data["status"] = "todo"
        super().__init__(**data)

    issue_id: str
    project_id: str
    title: str
    description: str
    status: str  # 例: "todo", "in_progress", "done"
    created_at: datetime
    updated_at: datetime
    
    @classmethod
    def set_repository(cls, repository: IssueRepository) -> None:
        """
        リポジトリを設定します。依存性注入のために使用します。
        
        Args:
            repository: 使用するIssueRepositoryの実装
        """
        cls._repository = repository
    
    @classmethod
    def get_repository(cls) -> IssueRepository:
        """
        現在のリポジトリを取得します。設定されていない場合はデフォルトのリポジトリを使用します。
        
        Returns:
            IssueRepository: 使用するリポジトリ
        """
        if cls._repository is None:
            cls._repository = get_issue_repository()
        return cls._repository
    
    def create(self) -> Self:
        """
        新しいIssueを作成します。
        
        Returns:
            Self: 作成されたIssueのインスタンス
        """
        self.get_repository().save_or_update(self)
        return self
    
    def save(self) -> Self:
        """
        Issueを永続化します。
        
        Returns:
            Self: 保存されたIssueのインスタンス
        """
        self.get_repository().save_or_update(self)
        return self
    
    def update(self, **kwargs) -> Self:
        """
        Issueを更新します。
        
        Returns:
            Self: 更新されたIssueのインスタンス
        """
        self.updated_at = datetime.now()
        for key, value in kwargs.items():
            setattr(self, key, value)
        return self.save()
    
    @classmethod
    def find_by_id(cls, project_id: str, issue_id: str) -> Optional["Issue"]:
        """
        プロジェクトIDとIssueIDによってIssueを検索します。
        
        Args:
            project_id: Issueが属するプロジェクトのID
            issue_id: 検索するIssueのID
            
        Returns:
            Optional[Self]: 見つかったIssue、または見つからない場合はNone
        """
        return cls.get_repository().get_by_id(project_id, issue_id)
    
    @classmethod
    def find_by_project_id(cls, project_id: str) -> List["Issue"]:
        """
        プロジェクトIDに関連する全てのIssueを取得します。
        
        Args:
            project_id: Issueが属するプロジェクトのID
            
        Returns:
            List[Self]: Issueのリスト
        """
        return cls.get_repository().get_by_project_id(project_id)
    
    def delete(self) -> None:
        """
        Issueを削除します。
        
        Returns:
            None
        """
        return self.get_repository().delete(self.project_id, self.issue_id)
