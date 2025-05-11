from datetime import datetime
from typing import Dict
from pydantic import BaseModel
from uuid import uuid4


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

