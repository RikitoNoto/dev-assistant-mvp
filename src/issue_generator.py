import json
import os
from chatbot import Chatbot
from dotenv import load_dotenv

try:
    from langchain_openai import ChatOpenAI
except ImportError:
    from langchain.chat_models import ChatOpenAI
from typing import Optional

load_dotenv()


class IssueTitleGenerator(Chatbot):
    """
    イシュー生成を支援するチャットボットクラス。
    """

    def __init__(self, plan: str, tech_spec: str):
        self.__last_message: Optional[str] = None
        self.__plan = plan
        self.__tech_spec = tech_spec
        super().__init__()

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
        あなたは企画と技術仕様からエンジニアが実行可能な具体的なイシュータイトルを生成するアシスタントです
        ユーザーのメッセージと現在のチケットの内容をもとに、イシューの追加や削除の提案をしてください

        イシューは具体的にエンジニアが何をすべきなのかがわかるようにしてください
        例えば、以下のようなイシューはNGです
        - 「ユーザー登録機能を実装する」
        - 「ユーザー登録機能のUIを作成する」
        以下のようなイシューはOKです
        - 「バックエンド：ユーザー登録を行うAPIの作成」
        - 「フロントエンド：ユーザー登録画面の作成」

        ## output
        - ユーザーへのメッセージの後に「===============」を出力しイシューの指示を記載
        - 1行ごとに以下の指示のみを出力します
        - + <イシュータイトル> はイシューの追加を示します
        - - <issue_id> はイシューの削除を示します

        ## 企画
        {self.__plan}
        ## 技術仕様
        {self.__tech_spec}
        """

    async def stream(self, user_message: str, history: list = None, **kwargs):
        response = ""
        current_issues = kwargs.get("current_issues", [])
        kwargs.pop("current_issues", None)

        # Format issues as JSON with title, issue_id, and status
        formatted_issues = []
        for issue in current_issues:
            formatted_issues.append({
                "title": issue.title,
                "issue_id": issue.issue_id,
                "status": issue.status
            })
        
        # Convert the list to a JSON string
        issue_str = json.dumps(formatted_issues, ensure_ascii=False)

        message = f"""
        ## 現在のイシュー
        {issue_str}
        ## user message
        {user_message}
        """
        # Pass the constructed message and the history to the base class stream method
        async for chunk in super().stream(message, history=history, **kwargs):
            response += chunk
            yield chunk
        self.__last_message = response


class IssueContentGenerator(Chatbot):
    """
    イシュー内容生成を支援するチャットボットクラス。
    """

    def __init__(self, plan: str, tech_spec: str):
        self.__last_message: Optional[str] = None
        self.__plan = plan
        self.__tech_spec = tech_spec
        super().__init__()

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
        あなたは企画と技術仕様とイシュータイトルからエンジニアが実行可能な具体的なイシュー内容を生成するアシスタントです
        イシューは具体的にエンジニアが何をすべきなのかがわかるようにしてください
        内容はINVEST原則に従ってください

        ## output
        - ユーザーへのメッセージの後に「===============」を出力しイシューの内容を記載

        ## 企画
        {self.__plan}
        ## 技術仕様
        {self.__tech_spec}
        """

    async def stream(self, user_message: str, history: list = None, **kwargs):
        response = ""
        issue_title = kwargs.get("issue_title", "")
        kwargs.pop("issue_title", None)

        message = f"""
        ## イシュータイトル
        {issue_title}
        ## user message
        {user_message}
        """
        # Pass the constructed message and the history to the base class stream method
        async for chunk in super().stream(message, history=history, **kwargs):
            response += chunk
            yield chunk
        self.__last_message = response

