import os
from chatbot import Chatbot
from typing import Optional

try:
    from langchain_openai import ChatOpenAI
except ImportError:
    from langchain.chat_models import ChatOpenAI
from dotenv import load_dotenv

load_dotenv()


class TechSpecBot(Chatbot):
    """
    プロダクト企画を支援するチャットボットクラス。
    """

    def __init__(self, plan: str):
        self.__plan = plan
        super().__init__()
        self.__last_message: Optional[str] = None

    @property
    def _model(self):
        """
        モデルのプロパティを取得する抽象メソッド。
        """
        return ChatOpenAI(
            model="gpt-4o-mini",
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            streaming=True,
            temperature=0.7,
        )

    @property
    def _SYSTEM_MESSAGE_PROMPT(self) -> str:
        return f"""
        あなたは技術仕様ファイルの修正をサポートするアシスタントです
        ユーザーから提案された企画から技術仕様ファイルを作成したり、技術仕様ファイルをブラッシュアップして技術仕様ファイルを出力します
        選定で重要視するのは、コストと開発スピードです。
        firebaseやsupabaseなどのBaaSを利用することも考慮してください。

        技術仕様は以下の点が分かるものを作成してください
        - フロント・バックエンド・インフラの技術スタック
        - (ログインが必要な場合) 認証方式と利用する技術スタック
        - (永続化が必要な場合)利用するデータベース
        - (状態管理が必要な場合)利用する状態管理ライブラリ
        - その他、特別必要な技術スタックと用途

        ## output
        - 会話の返答の後に企画の修正内容を返す
        - ユーザーへのメッセージの後に「===============」を出力しファイルの内容を記載
        - 「企画ファイル」のようなタイトルは不要

        ## 企画
        {self.__plan}
        """

    async def stream(self, user_message: str, history: list = None, **kwargs):
        response = ""
        content = kwargs.get("content", "")
        # Remove 'content' and 'history' from kwargs if they exist,
        # to avoid passing them down again if super().stream uses **kwargs directly.
        kwargs.pop("content", None)
        kwargs.pop("history", None)

        message = f"""
        ## 現在の技術仕様ファイル
        {content}
        ## user message
        {user_message}
        """
        # Pass the constructed message and the history to the base class stream method
        async for chunk in super().stream(message, history=history, **kwargs):
            response += chunk
            yield chunk
        self.__last_message = response

    def is_finished(self) -> bool:
        """
        技術仕様が完了したかどうかを判定するメソッド。
        """
        if self.__last_message is None:
            return False
        return self.__last_message.startswith("[完了]")
