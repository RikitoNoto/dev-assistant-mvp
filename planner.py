import os
from chatbot import Chatbot
from dotenv import load_dotenv

try:
    from langchain_openai import ChatOpenAI
except ImportError:
    from langchain.chat_models import ChatOpenAI
from typing import Optional

load_dotenv()


class PlannerBot(Chatbot):
    """
    プロダクト企画を支援するチャットボットクラス。
    """

    def __init__(self):
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
        return """
        あなたは企画ファイルの修正をサポートするアシスタントです
        ユーザーから提案された素案から企画ファイルを作成したり、企画ファイルをブラッシュアップして企画ファイルを出力します

        企画は以下の点が分かるものを作成してください
        - 概要
        - 課題
        - ターゲット
        - 提供する価値
        - メッセージ
        - MVPで作成するもの(対応するプラットフォームを含む)
        - 将来的に追加する機能

        ## output
        - 会話の返答の後に企画の修正内容を返す
        - ユーザーへのメッセージの後に「===============」を出力しファイルの内容を記載
        - 「企画ファイル」のようなタイトルは不要

        """

    async def stream(self, user_message: str):
        response = ""
        async for chunk in super().stream(user_message):
            response += chunk
            yield chunk
        self.__last_message = response

    def is_finished(self) -> bool:
        """
        企画が完了したかどうかを判定するメソッド。
        """
        if self.__last_message is None:
            return False
        return self.__last_message.startswith("[完了]")
