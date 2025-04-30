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
