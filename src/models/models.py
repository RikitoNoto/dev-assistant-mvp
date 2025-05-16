from __future__ import annotations
from datetime import datetime
from typing import List, Dict, Optional
from pydantic import BaseModel, Field
from uuid import uuid4


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
