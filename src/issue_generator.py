import os
from chatbot import Chatbot
from dotenv import load_dotenv

try:
    from langchain_openai import ChatOpenAI
except ImportError:
    from langchain.chat_models import ChatOpenAI
from typing import Optional

load_dotenv()


class IssueGenerator(Chatbot):
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
        - 会話の返答の後にイシューの修正内容を箇条書きで返してください
        - 箇条書きの内容全てがイシューとして出力されるので、鉤括弧などは不要です
        - ユーザーへのメッセージの後に「===============」を出力しイシューの箇条書きを記載
        - イシュータイトル以外の内容は出力しないでください

        ## 企画
        {self.__plan}
        ## 技術仕様
        {self.__tech_spec}
        """

    async def stream(self, user_message: str, history: list = None, **kwargs):
        response = ""
        current_issues = kwargs.get("current_issues", [])
        kwargs.pop("current_issues", None)

        # Group issues by status for display
        issues_by_status = {}
        for issue in current_issues:
            if issue.status not in issues_by_status:
                issues_by_status[issue.status] = []
            issues_by_status[issue.status].append(issue.title)
        
        issue_str = ""
        for status, titles in issues_by_status.items():
            issue_str += f"- {status}:\n"
            for title in titles:
                issue_str += f"\t- {title}\n"

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

    def is_finished(self) -> bool:
        """
        企画が完了したかどうかを判定するメソッド。
        """
        if self.__last_message is None:
            return False
        return self.__last_message.startswith("[完了]")
