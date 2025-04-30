from pydantic import BaseModel


class Document(BaseModel):
    """
    企画ドキュメントを表すデータモデル。
    """

    project_id: str | None = None  # 更新時はIDを指定、新規作成時はNone
    content: str


class UserMessage(BaseModel):
    """
    ユーザーからのメッセージを表すデータモデル。
    """

    message: str
