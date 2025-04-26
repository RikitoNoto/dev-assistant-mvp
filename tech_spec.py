import os
from chatbot import Chatbot
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

load_dotenv()


class TechSpecBot(Chatbot):
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
        あなたは優秀なエンジニアです。
        ユーザーから提案された企画から技術仕様を決めるサポートをしてください
        選定で重要視するのは、コストと開発スピードです。
        firebaseやsupabaseなどのBaaSを利用することも考慮してください。

        技術仕様は以下の点が分かるものを作成してください
        - フロント・バックエンド・インフラの技術スタック
        - (ログインが必要な場合) 認証方式と利用する技術スタック
        - (永続化が必要な場合)利用するデータベース
        - (状態管理が必要な場合)利用する状態管理ライブラリ
        - その他、特別必要な技術スタックと用途
        """
