from typing import TypedDict, Annotated, Sequence
import operator

from langchain_core.messages import BaseMessage, HumanMessage
from langgraph.graph import StateGraph, END
import chainlit as cl

from planner import PlannerBot
from tech_spec import TechSpecBot

# 環境変数をロード (必要に応じて)
from dotenv import load_dotenv

load_dotenv()


# 状態の定義
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    plan: str
    tech_spec: str


# ノードの定義 (非同期実行に対応させるため async def に変更)
async def run_planner(state: AgentState):
    """PlannerBotを実行するノード"""
    print("--- Running Planner ---")
    planner_bot = PlannerBot()
    # 最後のメッセージを取得してPlannerに渡す
    last_message = state["messages"][-1].content
    try:
        # ステップ開始を通知
        await cl.Message(content="企画プランニングを開始します...").send()

        response = ""
        msg = cl.Message(content="")
        await msg.send()
        async for chunk in planner_bot.stream(last_message):
            # 受け取ったチャンクをメッセージにストリーミング
            response += chunk
            await msg.stream_token(chunk)
        state["plan"] = response

    except Exception as e:
        print(f"Error in Planner: {e}")
        await cl.Message(
            content=f"プランナーの実行中にエラーが発生しました: {e}"
        ).send()
        # エラーが発生した場合、以降の処理をスキップするために state を変更するか、
        # 例外を投げて LangGraph のエラーハンドリングに任せる (設定が必要)
        # ここでは tech_spec を空にしておく
        state["plan"] = "プランニング中にエラーが発生しました。"
        state["tech_spec"] = ""  # エラー時は Tech Spec を実行しない想定
        # エラー発生時は END に遷移させるなどの工夫が必要になる場合がある
    return state


async def run_tech_spec(state: AgentState):
    """TechSpecBotを実行するノード"""
    # プランニングでエラーが発生していたらスキップ
    if not state["plan"] or "エラーが発生しました" in state["plan"]:
        print("--- Skipping Tech Spec due to previous error ---")
        state["tech_spec"] = "プランニングのエラーによりスキップされました。"
        # スキップした場合もユーザーに通知
        await cl.Message(
            content="プランニングでエラーが発生したため、技術仕様の生成をスキップします。"
        ).send()
        return state

    print("--- Running Tech Spec ---")
    tech_spec_bot = TechSpecBot()
    plan = state["plan"]
    tech_spec_input = f"以下の企画に基づいて技術仕様を作成してください:\n\n{plan}"
    try:
        # ステップ開始を通知
        await cl.Message(content="技術仕様の生成を開始します...").send()

        # PlannerBotのチェーンから直接ストリームを取得
        response = ""
        msg = cl.Message(content="")
        await msg.send()
        async for chunk in tech_spec_bot.stream(tech_spec_input):
            # 受け取ったチャンクをメッセージにストリーミング
            response += chunk
            await msg.stream_token(chunk)
        state["tech_spec"] = response
    except Exception as e:
        print(f"Error in Tech Spec: {e}")
        await cl.Message(content=f"技術仕様の生成中にエラーが発生しました: {e}").send()
        state["tech_spec"] = "技術仕様の生成中にエラーが発生しました。"

    return state


# グラフの構築 (非同期ノードを使用)
workflow = StateGraph(AgentState)

# ノードを追加
workflow.add_node("planner", run_planner)
workflow.add_node("tech", run_tech_spec)

# エッジを追加
workflow.add_edge("planner", "tech")
workflow.add_edge("tech", END)  # TechSpecの後に終了

# 開始点を設定
workflow.set_entry_point("planner")

# グラフをコンパイル
# 非同期実行のため acompile を使うのが望ましいが、
# LangGraph のバージョンによっては compile で非同期ノードも扱える
app = workflow.compile()


@cl.on_chat_start
async def start_chat():
    """チャット開始時の処理"""
    await cl.Message(
        content="こんにちは！どのようなアプリのアイデアがありますか？"
    ).send()
    # セッションにグラフインスタンスを保存することも可能
    # cl.user_session.set("graph_app", app)


@cl.on_message
async def main(message: cl.Message):
    """ユーザーからのメッセージ受信時の処理"""
    user_input = message.content
    if not user_input:
        return

    # グラフ実行の準備
    initial_state = {
        "messages": [HumanMessage(content=user_input)],
        "plan": "",
        "tech_spec": "",
    }

    # 進行中であることを示すメッセージ
    # await cl.Message(content="アイデアを処理中です...").send() # 各ステップで開始メッセージを出すので不要かも

    # LangGraphワークフローを非同期で実行し、イベントを処理
    async for event in app.astream(initial_state):
        # 各ステップの完了はノード関数内でメッセージ送信される
        # print(event) # デバッグ用
        pass

    # 全ての処理が終わったことを示すメッセージ (任意)
    await cl.Message(content="処理が完了しました。").send()


# Chainlitアプリケーションを実行するためのコマンド: chainlit run main.py -w
