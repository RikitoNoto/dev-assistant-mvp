import os
from chatbot import Chatbot
from langchain.chat_models.openai import ChatOpenAI
from dotenv import load_dotenv

load_dotenv()


class PlannerBot(Chatbot):
    """
    プロダクト企画を支援するチャットボットクラス。
    """

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
        あなたは優秀なプロダクトオーナーです。
        ユーザーから提案された素案をブラッシュアップして企画を作るサポートをしてください

        企画は以下の点が分かるものを作成してください
        - 概要
        - 課題
        - ターゲット
        - 提供する価値
        - メッセージ
        - MVPで作成するもの
        - 将来的に追加する機能
        """
