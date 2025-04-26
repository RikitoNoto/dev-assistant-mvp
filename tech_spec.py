import os
from chatbot import Chatbot
from typing import Optional
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

load_dotenv()


class TechSpecBot(Chatbot):
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
        あなたは優秀なエンジニアです。
        ユーザーから提案された企画から技術仕様を決めるサポートをしてください
        選定で重要視するのは、コストと開発スピードです。
        firebaseやsupabaseなどのBaaSを利用することも考慮してください。
        ユーザーの負荷が少ないように大まかには仕様を考えて、修正事項のフィードバックを求めるとよいです

        技術仕様は以下の点が分かるものを作成してください
        - フロント・バックエンド・インフラの技術スタック
        - (ログインが必要な場合) 認証方式と利用する技術スタック
        - (永続化が必要な場合)利用するデータベース
        - (状態管理が必要な場合)利用する状態管理ライブラリ
        - その他、特別必要な技術スタックと用途

        ## output
        - 全ての回答の冒頭に[完了]か[質問]を返してください
        - 質問がある場合は、最初に[質問]を返してください
        - 質問がある場合は一つずつ質問を返してください
        - 不明点もなく、完璧な技術仕様になった場合は、最初に[完了]を返してください
        - [完了]を返すときは、すでに話していても[完了]の下に必ず完全な技術仕様を返してください。
          [完了]以下に記載されたものが次の処理に渡されます
        """

    async def stream(self, user_message: str):
        response = ""
        async for chunk in super().stream(user_message):
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
