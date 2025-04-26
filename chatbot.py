from abc import ABC, abstractmethod
from typing import Iterator
from langchain_core.language_models.chat_models import BaseChatModel
from langchain.schema import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
)


class Chatbot(ABC):
    def __init__(self):
        self._messages: list[BaseMessage] = []
        self._messages.append(
            SystemMessage(content=self._SYSTEM_MESSAGE_PROMPT),
        )

    @property
    @abstractmethod
    def _model(self) -> BaseChatModel:
        """
        モデルのプロパティを取得する抽象メソッド。
        """
        pass

    @property
    @abstractmethod
    def _SYSTEM_MESSAGE_PROMPT(self) -> str:
        """
        システムメッセージのプロンプトを取得する抽象メソッド。
        """
        pass

    async def stream(self, user_message: str):
        """
        ユーザーメッセージを処理し、ストリーミングで応答を生成します。

        Args:
            user_message: ユーザーからの入力メッセージ。

        Returns:
            生成された応答テキスト。
        """
        response_content = ""
        self._messages.append(HumanMessage(content=user_message))
        for chunk in self._model.stream(self._messages):
            response_content += chunk.text()
            yield chunk.text()
        self._messages.append(AIMessage(content=response_content))
