from pydantic import BaseModel


class Document(BaseModel):
    """
    企画ドキュメントを表すデータモデル。
    """

    project_id: str
    content: str


class UserMessage(BaseModel):
    """
    ユーザーからのメッセージを表すデータモデル。
    """

    message: str


from uuid import UUID, uuid4
from datetime import datetime


class Project(BaseModel):
    """
    プロジェクトを表すデータモデル。
    """

    project_id: UUID = uuid4()
    title: str
    created_at: datetime = datetime.now()
    updated_at: datetime = datetime.now()
