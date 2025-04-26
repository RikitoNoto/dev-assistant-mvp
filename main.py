from typing import TypedDict, Annotated, Sequence
import operator

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, END
import chainlit as cl

from planner import PlannerBot
from tech_spec import TechSpecBot

from dotenv import load_dotenv

load_dotenv()


# 状態定義
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    plan: str
    tech_spec: str
    is_plan_finished: bool


async def run_planner(state: AgentState):
    print("--- Running Planner ---")
    planner_bot: PlannerBot = cl.user_session.get("planner_bot")
    if planner_bot is None:
        raise RuntimeError("PlannerBotが初期化されていません。")

    last_message = state["messages"][-1].content
    response = ""
    is_finished = False

    try:
        msg = cl.Message(content="プランニング中...")
        await msg.send()

        async for chunk in planner_bot.stream(last_message):
            response += chunk
            await msg.stream_token(chunk)

        # 進行中メッセージを更新完了
        await msg.update()

        # # 結果を別メッセージとして表示
        # result_msg = cl.Message(content=response)
        # await result_msg.send()

        # 「完了」キーワードを見て強制的にフラグを立てる
        if "[完了]" in response:
            is_finished = True

        new_messages = state["messages"] + [AIMessage(content=response)]

        return {
            **state,
            "messages": new_messages,
            "plan": response,
            "is_plan_finished": is_finished,
        }
    except Exception as e:
        print(f"Error in Planner: {e}")
        await cl.Message(content=f"プランナーエラー: {e}").send()
        return {
            **state,
            "plan": "プランニング失敗",
            "tech_spec": "",
            "is_plan_finished": False,
        }


async def run_tech_spec(state: AgentState):
    print("--- Running Tech Spec ---")
    tech_spec_bot: TechSpecBot = cl.user_session.get("tech_spec_bot")
    if tech_spec_bot is None:
        raise RuntimeError("TechSpecBotが初期化されていません。")

    plan_content = state["plan"].replace("[完了]", "").strip()
    response = ""
    try:
        msg = cl.Message(content="技術仕様作成中...")
        await msg.send()

        async for chunk in tech_spec_bot.stream(plan_content):
            response += chunk
            await msg.stream_token(chunk)

        # 完了メッセージを明示的に送信
        await msg.update()

        # # 技術仕様の結果を別のメッセージとして表示
        # result_msg = cl.Message(content=response)
        # await result_msg.send()

        new_messages = state["messages"] + [AIMessage(content=response)]

        return {
            **state,
            "messages": new_messages,
            "tech_spec": response,
        }
    except Exception as e:
        print(f"Error in Tech Spec: {e}")
        await cl.Message(content=f"技術仕様エラー: {e}").send()
        return {
            **state,
            "tech_spec": "技術仕様生成失敗",
        }


def should_run_tech_spec(state: AgentState) -> str:
    print(f"--- is_plan_finished: {state['is_plan_finished']} ---")
    return "tech" if state["is_plan_finished"] else END


# グラフ作成
workflow = StateGraph(AgentState)
workflow.add_node("planner", run_planner)
workflow.add_node("tech", run_tech_spec)

workflow.add_conditional_edges(
    "planner", should_run_tech_spec, {"tech": "tech", END: END}
)
workflow.add_edge("tech", END)

workflow.set_entry_point("planner")
app = workflow.compile()


@cl.on_chat_start
async def start_chat():
    await cl.Message(content="こんにちは！アイデアを教えてください！").send()
    cl.user_session.set("planner_bot", PlannerBot())
    cl.user_session.set("tech_spec_bot", TechSpecBot())


@cl.on_message
async def main(message: cl.Message):
    user_input = message.content
    if not user_input:
        return

    # ここでセッションから前回の状態を取る
    previous_state = cl.user_session.get("agent_state")

    if previous_state is None:
        # セッションに何もなければ新規作成
        agent_state = AgentState(
            messages=[HumanMessage(content=user_input)],
            plan="",
            tech_spec="",
            is_plan_finished=False,
        )
    else:
        # 前回のmessagesに追記していく
        agent_state = {
            **previous_state,
            "messages": previous_state["messages"] + [HumanMessage(content=user_input)],
        }

    final_state = None

    # グラフ実行
    final_state = agent_state  # 初期値として現在の状態を設定
    async for event in app.astream(agent_state):
        # 各ノードの実行後の状態を取得
        if isinstance(event, dict):
            if event.get("planner"):
                final_state = event["planner"]
            elif event.get("tech"):
                final_state = event["tech"]

    print(f"Final State: {final_state}")
    if final_state:
        # セッションに保存（次回使うため）
        cl.user_session.set("agent_state", final_state)
