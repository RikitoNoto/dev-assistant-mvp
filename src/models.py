import random
import string
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
