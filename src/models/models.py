from datetime import datetime
from typing import List, Dict, Optional
from pydantic import BaseModel, Field
from uuid import uuid4


class Document(BaseModel):
    """
    企画ドキュメントを表すデータモデル。
    """

    project_id: str
    content: str


class ChatAndEdit(BaseModel):
    """
    チャットと編集を行うためのデータモデル。
    """

    project_id: str
    message: str
    history: Optional[List[Dict[str, str]]] = Field(default_factory=list)


class UserMessage(BaseModel):
    """
    ユーザーからのメッセージを表すデータモデル。
    """

    message: str


class Project(BaseModel):
    """
    プロジェクトを表すデータモデル。
    """

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
    def create(cls, title: str) -> 'Project':
        """
        新しいプロジェクトを作成します。
        
        Args:
            title: プロジェクトのタイトル
            
        Returns:
            作成されたプロジェクトのインスタンス
        """
        return cls(title=title)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Project':
        """
        辞書からプロジェクトのインスタンスを作成します。
        
        Args:
            data: プロジェクトデータを含む辞書
            
        Returns:
            プロジェクトのインスタンス
        """
        return cls(**data)
    
    def to_dict(self) -> Dict:
        """
        プロジェクトのインスタンスを辞書に変換します。
        
        Returns:
            プロジェクトデータを含む辞書
        """
        return self.dict()
    
    def update(self, title: str = None) -> None:
        """
        プロジェクトの情報を更新します。
        
        Args:
            title: 新しいプロジェクトのタイトル（指定しない場合は変更なし）
        """
        if title is not None:
            self.title = title
        self.updated_at = datetime.now()
    
    @classmethod
    def generate_project_id(cls) -> str:
        """
        プロジェクトIDを生成します。
        
        Returns:
            生成されたプロジェクトID
        """
        return str(uuid4())


class Issue(BaseModel):
    """
    Issueを表すデータモデル。
    """

    def __init__(self, **data):
        if "issue_id" not in data:
            data["issue_id"] = self.generate_issue_id()
        if "created_at" not in data:
            data["created_at"] = datetime.now()
        if "updated_at" not in data:
            data["updated_at"] = datetime.now()
        if "description" not in data:
            data["description"] = ""
        if "status" not in data:
            data["status"] = "todo"
        super().__init__(**data)
        
    @classmethod
    def generate_issue_id(cls):
        return  str(uuid4())

    issue_id: str
    project_id: str
    title: str
    description: str
    status: str  # 例: "open", "in_progress", "closed"
    created_at: datetime
    updated_at: datetime
