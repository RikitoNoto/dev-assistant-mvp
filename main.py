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
planner_bot = PlannerBot()


# 状態の定義
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    plan: str
    tech_spec: str
    is_plan_finished: bool  # Plannerが完了したかどうかのフラグを追加


# ノードの定義 (非同期実行に対応させるため async def に変更)
async def run_planner(state: AgentState):
    """PlannerBotを実行するノード"""
    print("--- Running Planner ---")
    # 最後のメッセージを取得してPlannerに渡す
    last_message = state["messages"][-1].content
    try:
        response = ""
        msg = cl.Message(content="")
        await msg.send()
        async for chunk in planner_bot.stream(last_message):
            # 受け取ったチャンクをメッセージにストリーミング
            response += chunk
            await msg.stream_token(chunk)
        state["plan"] = response
        state["is_plan_finished"] = planner_bot.is_finished()  # 完了状態を記録

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
        state["is_plan_finished"] = False  # エラー時は未完了扱い
    return state


async def run_tech_spec(state: AgentState):
    """TechSpecBotを実行するノード"""
    # プランニングでエラーが発生していたらスキップ (このチェックは不要になるかも)
    # if not state["plan"] or "エラーが発生しました" in state["plan"]:
    #     print("--- Skipping Tech Spec due to previous error ---")
    #     state["tech_spec"] = "プランニングのエラーによりスキップされました。"
    #     await cl.Message(
    #         content="プランニングでエラーが発生したため、技術仕様の生成をスキップします。"
    #     ).send()
    #     return state

    print("--- Running Tech Spec ---")
    tech_spec_bot = TechSpecBot()
    plan = state["plan"]
    # [完了] プレフィックスを除去して TechSpec に渡す
    plan_content = plan.replace("[完了]", "").strip()
    tech_spec_input = (
        f"以下の企画に基づいて技術仕様を作成してください:\n\n{plan_content}"
    )
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


# 条件分岐用の関数
def should_run_tech_spec(state: AgentState) -> str:
    """Plannerの結果に基づいてTech Specを実行するかどうかを決定"""
    print(f"--- Checking if plan is finished: {state['is_plan_finished']} ---")
    if state["is_plan_finished"]:
        # プランニングが完了していればTech Specへ
        return "tech"
    else:
        # プランニングが未完了（質問など）の場合はグラフを終了し、ユーザーの入力を待つ
        return END  # "planner" から END に変更


# グラフの構築 (非同期ノードを使用)
workflow = StateGraph(AgentState)

# ノードを追加
workflow.add_node("planner", run_planner)
workflow.add_node("tech", run_tech_spec)

# エッジを追加
workflow.add_conditional_edges(
    "planner",  # 開始ノード
    should_run_tech_spec,  # 条件分岐関数
    {
        "tech": "tech",  # 条件分岐関数が "tech" を返した場合、tech ノードへ
        END: END,  # 条件分岐関数が END を返した場合（プラン未完了含む）、終了
    },
)
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
    global planner_bot
    planner_bot = PlannerBot()


@cl.on_message
async def main(message: cl.Message):
    """ユーザーからのメッセージ受信時の処理"""
    user_input = message.content
    if not user_input:
        return

    # グラフ実行の準備
    initial_state = AgentState(  # AgentStateで初期化
        messages=[HumanMessage(content=user_input)],
        plan="",
        tech_spec="",
        is_plan_finished=False,  # 初期値は False
    )

    final_state = None  # 最終状態を保持する変数
    # LangGraphワークフローを非同期で実行し、イベントを処理
    async for event in app.astream(initial_state):
        # print(event) # デバッグ用
        # 最終状態を取得 (ENDに到達したときの state)
        # LangGraphのバージョンやイベント構造によってキーが異なる可能性がある
        if event.get("event") == "on_chain_end" or event.get("event") == "on_graph_end":
            output = event.get("data", {}).get("output")
            # outputがAgentStateの形式であることを確認
            if isinstance(output, dict) and "messages" in output:
                final_state = output


# Chainlitアプリケーションを実行するためのコマンド: chainlit run main.py -w
