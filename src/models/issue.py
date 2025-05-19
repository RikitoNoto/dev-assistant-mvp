from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel
from routers.utils import get_issue_repository
from repositories.data.issues import IssueRepository
from typing import Optional, ClassVar, Self, List, Dict, Any
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
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Issueをディクショナリに変換します。
        
        Returns:
            Dict[str, Any]: Issueのデータを含むディクショナリ
        """
        return {
            "issue_id": self.issue_id,
            "project_id": self.project_id,
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Self:
        """
        ディクショナリからIssueを作成します。
        
        Args:
            data: Issueデータを含むディクショナリ
            
        Returns:
            Self: 作成されたIssueインスタンス
        """
        # ISO形式の日付文字列をdatetimeオブジェクトに変換
        created_at = data["created_at"]
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
            
        updated_at = data["updated_at"]
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at)
            
        return cls(
            issue_id=data["issue_id"],
            project_id=data["project_id"],
            title=data["title"],
            description=data.get("description", ""),
            status=data.get("status", "todo"),
            created_at=created_at,
            updated_at=updated_at
        )
    
    def create(self) -> Self:
        """
        新しいIssueを作成します。
        
        Returns:
            Self: 作成されたIssueのインスタンス
        """
        self.get_repository().save_or_update(self.to_dict())
        return self
    
    def save(self) -> Self:
        """
        Issueを永続化します。
        
        Returns:
            Self: 保存されたIssueのインスタンス
        """
        self.get_repository().save_or_update(self.to_dict())
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
        issue_data = cls.get_repository().get_by_id(project_id, issue_id)
        if issue_data is None:
            return None
        return cls.from_dict(issue_data)
    
    @classmethod
    def find_by_project_id(cls, project_id: str) -> List["Issue"]:
        """
        プロジェクトIDに関連する全てのIssueを取得します。
        
        Args:
            project_id: Issueが属するプロジェクトのID
            
        Returns:
            List[Self]: Issueのリスト
        """
        issues_data = cls.get_repository().get_by_project_id(project_id)
        return [cls.from_dict(item) for item in issues_data]
    
    def delete(self) -> None:
        """
        Issueを削除します。
        
        Returns:
            None
        """
        return self.get_repository().delete(self.project_id, self.issue_id)
