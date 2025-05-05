from abc import ABC, abstractmethod
from typing import Any
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

    async def stream(self, user_message: str, history: list = None, **kwargs):
        """
        ユーザーメッセージと履歴を処理し、ストリーミングで応答を生成します。

        Args:
            user_message: ユーザーからの入力メッセージ。
            history: 過去の対話履歴のリスト (例: [{"user": "msg"}, {"ai": "msg"}])。

        Returns:
            生成された応答テキスト。
        """
        # Reset messages for each stream call to include only system prompt initially
        current_messages = [SystemMessage(content=self._SYSTEM_MESSAGE_PROMPT)]

        # Add history messages if provided
        if history:
            for msg in history:
                if "user" in msg:
                    current_messages.append(HumanMessage(content=msg["user"]))
                elif "ai" in msg:
                    current_messages.append(AIMessage(content=msg["ai"]))

        # Add the current user message
        current_messages.append(HumanMessage(content=user_message))

        response_content = ""
        # Use the constructed messages for the current stream
        async for chunk in self._model.astream(current_messages, **kwargs):
            # Assuming chunk is already a string or has a text() method/attribute
            # Adjust based on the actual return type of _model.astream
            chunk_text = chunk.content if hasattr(chunk, "content") else str(chunk)
            response_content += chunk_text
            yield chunk_text

        # Append the final AI response to the current messages list for context,
        # but note this instance's _messages is not persisted across requests here.
        # If persistence is needed, it should be handled differently.
        current_messages.append(AIMessage(content=response_content))
        # Update self._messages if you need to maintain state within the instance,
        # though typically for stateless API calls, this might not be necessary.
        self._messages = current_messages
