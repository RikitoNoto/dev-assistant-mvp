import os
import chainlit as cl
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langgraph.graph import StateGraph, END  # ENDは後で使用
from typing import TypedDict, Annotated, List  # Unionは未使用なので削除

# import requests # requestsは不要になった
from dotenv import load_dotenv
import json  # jsonは後でストリーミング処理で使用
import httpx  # httpxを直接使用

# .envファイルから環境変数を読み込む
load_dotenv()

# APIキーを環境変数から取得 (後で設定)
PLANNING_APP_API_KEY = os.getenv("PLANNING_APP_API_KEY", "YOUR_PLANNING_APP_API_KEY")
SPEC_APP_API_KEY = os.getenv("SPEC_APP_API_KEY", "YOUR_SPEC_APP_API_KEY")
TASK_APP_API_KEY = os.getenv("TASK_APP_API_KEY", "YOUR_TASK_APP_API_KEY")
ISSUE_APP_API_KEY = os.getenv("ISSUE_APP_API_KEY", "YOUR_ISSUE_APP_API_KEY")

DIFY_API_ENDPOINT = "http://localhost/v1/chat-messages"  # Dify APIのエンドポイント


# LangGraphの状態を定義
class AppState(TypedDict):
    initial_query: str  # ユーザーの最初の入力
    plan_conversation_history: Annotated[
        List[BaseMessage], lambda x, y: x + y
    ]  # 企画アプリの対話履歴
    plan_output: str  # 企画アプリの最終出力 (企画書)
    spec_conversation_history: Annotated[
        List[BaseMessage], lambda x, y: x + y
    ]  # 仕様アプリの対話履歴
    spec_output: str  # 仕様アプリの最終出力 (技術仕様書)
    task_output: str  # タスク分解アプリの出力
    issue_output: str  # Issue出力アプリの出力
    current_step: str  # 現在の処理ステップ
    next_step: str  # 次の処理ステップ or ユーザーへの質問フラグ
    error_message: str  # エラーメッセージ


# --- Dify API呼び出し関数 ---
async def call_dify_api(
    api_key: str,
    query: str,
    conversation_id: str = "",
    inputs: dict = None,
    history: List[BaseMessage] = None,  # Dify APIでは直接使わないが拡張性考慮
    user: str = "chainlit-user",  # ユーザーIDを固定または動的に設定
) -> dict:
    """Dify APIを呼び出す共通関数 (ストリーミング対応)"""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "inputs": inputs if inputs else {},
        "query": query,
        "response_mode": "streaming",
        "conversation_id": conversation_id if conversation_id else "",
        "user": user,
        "files": [],  # ファイルアップロードは今回未使用
    }

    full_response_content = ""
    conversation_id_out = conversation_id  # レスポンスから取得できれば更新

    # httpx.AsyncClientを直接使用
    async with httpx.AsyncClient() as client:
        async with client.stream(
            "POST", DIFY_API_ENDPOINT, headers=headers, json=payload, timeout=300
        ) as response:
            response.raise_for_status()  # エラーチェック
            async for line in response.aiter_lines():  # httpxのストリーム処理
                if line:
                    # decoded_line = line.decode("utf-8") # aiter_lines はデコード済み
                    if line.startswith("data:"):
                        try:
                            data_str = line[len("data: ") :]
                            if not data_str:  # 空のdata行をスキップ
                                continue
                            data = json.loads(data_str)
                            event = data.get("event")
                            if event == "agent_message" or event == "message":
                                full_response_content += data.get("answer", "")
                            elif event == "message_end":
                                conversation_id_out = data.get(
                                    "conversation_id", conversation_id_out
                                )
                                # 他のメタデータが必要な場合はここで取得
                        except json.JSONDecodeError:
                            print(f"Failed to decode JSON: {data_str}")
                            # エラー処理が必要な場合
                        except Exception as e:
                            print(f"Error processing stream data: {e}")
                            # その他のエラー処理

    return {
        "answer": full_response_content,
        "conversation_id": conversation_id_out,
        "error": None,
    }


# --- Dify API呼び出し関数 (Completion用) ---
async def call_completion_api(
    api_key: str,
    inputs: dict,
    user: str = "chainlit-user",
) -> dict:
    """Dify Completion APIを呼び出す関数 (ストリーミング対応)"""
    COMPLETION_API_ENDPOINT = "http://localhost/v1/completion-messages"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    # 新しいペイロード形式
    payload = {
        "inputs": inputs,
        "response_mode": "streaming",
        "user": user,
        # "conversation_id" は completion API では通常不要
        # "query" も inputs に含める想定
    }

    full_response_content = ""
    # conversation_id は completion API のレスポンスに含まれない想定
    # conversation_id_out = ""

    async with httpx.AsyncClient() as client:
        try:
            async with client.stream(
                "POST",
                COMPLETION_API_ENDPOINT,
                headers=headers,
                json=payload,
                timeout=300,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line and line.startswith("data:"):
                        try:
                            data_str = line[len("data: ") :]
                            if not data_str:
                                continue
                            data = json.loads(data_str)
                            event = data.get("event")
                            # completion API のイベント名が異なる可能性あり
                            # chat API と同じ 'agent_message'/'message' を想定
                            if event == "agent_message" or event == "message":
                                full_response_content += data.get("answer", "")
                            # completion API の終了イベントも異なる可能性あり
                            # elif event == "message_end":
                            #     # conversation_id は通常ない
                            #     pass
                        except json.JSONDecodeError:
                            print(f"Failed to decode JSON: {data_str}")
                        except Exception as e:
                            print(f"Error processing stream data: {e}")
            return {
                "answer": full_response_content,
                # "conversation_id": conversation_id_out, # completion APIでは返らない
                "error": None,
            }
        except httpx.HTTPStatusError as e:
            print(f"HTTP error: {e.response.status_code} - {e.response.text}")
            return {"answer": "", "error": f"HTTP error: {e.response.status_code}"}
        except Exception as e:
            print(f"An error occurred: {e}")
            return {"answer": "", "error": str(e)}


# --- LangGraphノード関数 ---
async def planning_step(state: AppState) -> AppState:
    """企画ブラッシュアップステップ"""
    print("--- Planning Step ---")
    # UI更新はメインスレッドで行うべきだが、ここでは一旦ノード内で実行
    await cl.Message(content="企画ブラッシュアップアプリを実行中...").send()
    current_history = state.get("plan_conversation_history", [])
    if not current_history:  # 最初のクエリ
        query = state["initial_query"]
        # 履歴はrun_graph側で初期化
        # current_history.append(HumanMessage(content=query))
    else:  # ユーザーからの返信
        query = current_history[-1].content

    # Dify API呼び出し
    # conversation_idは履歴の最後のAIメッセージから取得、なければ新規
    last_ai_message = next(
        (msg for msg in reversed(current_history) if isinstance(msg, AIMessage)), None
    )
    conversation_id = (
        last_ai_message.additional_kwargs.get("conversation_id", "")
        if last_ai_message
        else ""
    )

    response = await call_dify_api(
        PLANNING_APP_API_KEY, query, conversation_id=conversation_id
    )

    if response["error"]:
        return {**state, "error_message": response["error"], "next_step": "error"}

    ai_response_text = response["answer"]
    new_conversation_id = response["conversation_id"]

    # 応答を履歴に追加
    ai_message = AIMessage(
        content=ai_response_text,
        additional_kwargs={"conversation_id": new_conversation_id},
    )
    updated_history = current_history + [ai_message]  # 新しいリストを作成

    # 応答の接頭辞を確認
    if ai_response_text.startswith("終了"):
        plan_output = ai_response_text[len("終了") :].strip()
        print(f"Planning finished. Output:\n{plan_output}")
        await cl.Message(
            content=f"企画書が完成しました。\n```\n{plan_output}\n```"
        ).send()
        return {
            **state,
            "plan_conversation_history": updated_history,
            "plan_output": plan_output,
            "current_step": "planning",
            "next_step": "spec",
        }
    elif ai_response_text.startswith("質問"):
        question = ai_response_text[len("質問") :].strip()
        print(f"Planning asking question: {question}")
        await cl.Message(content=f"企画担当からの質問:\n{question}").send()
        return {
            **state,
            "plan_conversation_history": updated_history,
            "current_step": "planning",
            "next_step": "ask_user",
        }
    else:
        # 想定外の応答
        print(f"Unexpected response from planning app: {ai_response_text}")
        await cl.Message(
            content=f"企画アプリから予期しない応答がありました:\n{ai_response_text}\n処理を継続します。"
        ).send()
        # エラーとせず、そのまま企画書として扱うか、エラーにするか要検討。
        # 一旦企画書として扱う。
        return {
            **state,
            "plan_conversation_history": updated_history,
            "plan_output": ai_response_text,
            "current_step": "planning",
            "next_step": "spec",
        }


async def spec_step(state: AppState) -> AppState:
    """技術仕様書作成ステップ"""
    print("--- Spec Step ---")
    await cl.Message(content="技術仕様書作成アプリを実行中...").send()
    current_history = state.get("spec_conversation_history", [])
    plan_output = state.get("plan_output", "")

    if not plan_output:
        return {
            **state,
            "error_message": "企画書が見つかりません。",
            "next_step": "error",
        }

    if not current_history:  # 最初の呼び出し (企画書を入力とする)
        query = f"以下の企画書に基づいて技術仕様を作成してください:\n\n{plan_output}"
        # 内部的な初期メッセージは履歴に加えない
        # current_history.append(HumanMessage(content=query))
    else:  # ユーザーからの返信
        query = current_history[-1].content

    # Dify API呼び出し
    last_ai_message = next(
        (msg for msg in reversed(current_history) if isinstance(msg, AIMessage)), None
    )
    conversation_id = (
        last_ai_message.additional_kwargs.get("conversation_id", "")
        if last_ai_message
        else ""
    )

    response = await call_dify_api(
        SPEC_APP_API_KEY, query, conversation_id=conversation_id
    )

    if response["error"]:
        return {**state, "error_message": response["error"], "next_step": "error"}

    ai_response_text = response["answer"]
    new_conversation_id = response["conversation_id"]

    # 応答を履歴に追加
    ai_message = AIMessage(
        content=ai_response_text,
        additional_kwargs={"conversation_id": new_conversation_id},
    )
    updated_history = current_history + [ai_message]

    # 応答の接頭辞を確認
    if ai_response_text.startswith("終了"):
        spec_output = ai_response_text[len("終了") :].strip()
        print(f"Spec finished. Output:\n{spec_output}")
        await cl.Message(
            content=f"技術仕様書が完成しました。\n```\n{spec_output}\n```"
        ).send()
        return {
            **state,
            "spec_conversation_history": updated_history,
            "spec_output": spec_output,
            "current_step": "spec",
            "next_step": "task",
        }
    elif ai_response_text.startswith("質問"):
        question = ai_response_text[len("質問") :].strip()
        print(f"Spec asking question: {question}")
        await cl.Message(content=f"技術仕様担当からの質問:\n{question}").send()
        return {
            **state,
            "spec_conversation_history": updated_history,
            "current_step": "spec",
            "next_step": "ask_user",
        }
    else:
        # 想定外の応答
        print(f"Unexpected response from spec app: {ai_response_text}")
        await cl.Message(
            content=f"技術仕様アプリから予期しない応答がありました:\n{ai_response_text}\n処理を継続します。"
        ).send()
        # エラーとせず、そのまま技術仕様書として扱う
        return {
            **state,
            "spec_conversation_history": updated_history,
            "spec_output": ai_response_text,
            "current_step": "spec",
            "next_step": "task",
        }


async def task_step(state: AppState) -> AppState:
    """タスク分解ステップ"""
    print("--- Task Step ---")
    await cl.Message(content="タスク分解アプリを実行中...").send()
    plan_output = state.get("plan_output", "")
    spec_output = state.get("spec_output", "")

    if not plan_output or not spec_output:
        return {
            **state,
            "error_message": "企画書または技術仕様書が見つかりません。",
            "next_step": "error",
        }

    # Dify Completion API呼び出し (inputsを使用)
    # query は inputs に含めるか、API側で解釈する想定
    inputs = {"plan": plan_output, "tech_spec": spec_output}
    # 必要であれば固定の指示を inputs に追加
    # inputs["instruction"] = "企画書と技術仕様書からタスクを分解してください。"

    response = await call_completion_api(TASK_APP_API_KEY, inputs=inputs)

    if response["error"]:
        return {**state, "error_message": response["error"], "next_step": "error"}

    task_output = response["answer"]
    print(f"Task decomposition finished. Output:\n{task_output}")
    await cl.Message(
        content=f"タスク分解が完了しました。\n```\n{task_output}\n```"
    ).send()

    return {
        **state,
        "task_output": task_output,
        "current_step": "task",
        "next_step": "issue",  # 次のステップへ
    }


async def issue_step(state: AppState) -> AppState:
    """Issue出力ステップ"""
    print("--- Issue Step ---")
    await cl.Message(content="Issue出力アプリを実行中...").send()
    plan_output = state.get("plan_output", "")
    spec_output = state.get("spec_output", "")
    task_output = state.get("task_output", "")

    if not task_output:
        return {
            **state,
            "error_message": "タスクリストが見つかりません。",
            "next_step": "error",
        }

    # Dify Completion API呼び出し (inputsを使用)
    # query は inputs に含めるか、API側で解釈する想定
    inputs = {
        "plan": plan_output,
        "tech_spec": spec_output,
        "tasks": task_output,
        # 必要であれば固定の指示を追加
        # "instruction": "タスクリストを基にIssue詳細を作成してください:",
    }
    tasks = json.loads(task_output)["issues"]
    issues: dict[str, str] = {}
    for task in tasks:

        response = await call_completion_api(
            ISSUE_APP_API_KEY,
            inputs={
                **inputs,
                "title": task,
            },
        )
        issue_output = response["answer"]
        issues[task] = issue_output
        print(f"Issue generation finished. Output:\n{issue_output}")

    if response["error"]:
        return {**state, "error_message": response["error"], "next_step": "error"}

    # 完了メッセージは run_graph 関数で表示

    return {
        **state,
        "issue_output": issues,
        "current_step": "issue",
        "next_step": "end",  # 最終ステップなのでend
    }


# --- 条件分岐ロジック ---
def should_continue_or_ask(state: AppState) -> str:
    """企画/仕様ステップ後、継続するかユーザーに質問するかを判断"""
    next_step = state.get("next_step")
    if state.get("error_message"):
        return "error"  # エラーが発生したら終了
    if next_step == "ask_user":
        print("Decision: Ask User")
        return "ask_user"  # ユーザーに質問
    elif next_step == "spec":
        print("Decision: Continue to Spec")
        return "spec"  # 仕様ステップへ
    elif next_step == "task":
        print("Decision: Continue to Task")
        return "task"  # タスク分解ステップへ
    elif next_step == "issue":
        print("Decision: Continue to Issue")
        return "issue"  # Issue出力ステップへ
    elif next_step == "end":
        print("Decision: End")
        return END  # 終了
    else:
        print("Decision: Error (Unknown next step)")
        # 予期しない状態の場合はエラーとして終了させる
        # state["error_message"] = f"不明な次のステップ: {next_step}" # 更新不可
        return "error"


# --- LangGraphグラフ構築 ---
workflow = StateGraph(AppState)

# ノードを追加
workflow.add_node("planning", planning_step)
workflow.add_node("spec", spec_step)
workflow.add_node("task", task_step)
workflow.add_node("issue", issue_step)
# error_node はエラーメッセージをコンソールに出力し、状態をそのまま返す
workflow.add_node(
    "error_node",
    lambda state: print(f"Error Node Triggered: {state.get('error_message')}"),
)

# エントリーポイントを設定
workflow.set_entry_point("planning")

# エッジを追加
# planning ステップ後の分岐
workflow.add_conditional_edges(
    "planning",
    should_continue_or_ask,
    {
        "spec": "spec",
        "ask_user": END,  # ユーザー入力待ちのためグラフを一旦終了
        "error": "error_node",
    },
)
# spec ステップ後の分岐 (planningと同様の分岐ロジックを想定)
workflow.add_conditional_edges(
    "spec",
    should_continue_or_ask,
    {
        "task": "task",
        "ask_user": END,  # ユーザー入力待ちのためグラフを一旦終了
        "error": "error_node",
    },
)
# task ステップ後は issue ステップへ
workflow.add_conditional_edges(
    "task",
    should_continue_or_ask,  # next_stepを見て判断
    {"issue": "issue", "error": "error_node"},
)
# issue ステップ後は終了
workflow.add_conditional_edges(
    "issue",
    should_continue_or_ask,  # next_stepを見て判断
    {END: END, "error": "error_node"},
)
# エラーノードからは終了
workflow.add_edge("error_node", END)


# --- Chainlit UI ---
@cl.on_chat_start
async def start_chat():
    # グラフをコンパイルしてセッションに保存
    # コンパイル済みのグラフがない場合のみコンパイル
    if cl.user_session.get("graph_runner") is None:  # 存在確認
        try:
            app = workflow.compile()
            cl.user_session.set("graph_runner", app)
        except Exception as e:
            print(f"Error compiling graph: {e}")
            await cl.Message(content=f"グラフのコンパイルエラー: {e}").send()
            return  # コンパイル失敗時は中断

    cl.user_session.set(
        "app_state",
        AppState(
            initial_query="",
            plan_conversation_history=[],
            plan_output="",
            spec_conversation_history=[],
            spec_output="",
            task_output="",
            issue_output="",
            current_step="start",  # 初期状態はstart
            next_step="",
            error_message="",
        ),
    )
    await cl.Message(content="企画の素案を入力してください。").send()


@cl.on_message
async def main(message: cl.Message):
    app_state = cl.user_session.get("app_state")
    graph_runner = cl.user_session.get("graph_runner")

    if not graph_runner:
        await cl.Message(content="アプリ初期化失敗: グラフ未コンパイル").send()
        return

    current_step_logic = app_state.get(
        "current_step", "start"
    )  # どのロジックを実行中か
    next_step_flag = app_state.get("next_step")  # グラフからの指示

    # ユーザー入力が必要な状態かチェック
    if next_step_flag == "ask_user":
        updated_state = app_state.copy()  # 状態をコピーして変更
        if current_step_logic == "planning":
            print("User responded to planning question.")
            # 履歴はイミュータブルに扱う
            updated_state["plan_conversation_history"] = app_state[
                "plan_conversation_history"
            ] + [HumanMessage(content=message.content)]
            updated_state["current_step"] = "planning"  # 再度企画ステップから
            updated_state["next_step"] = ""  # フラグリセット
            await run_graph(updated_state)  # グラフ実行再開
        elif current_step_logic == "spec":
            print("User responded to spec question.")
            updated_state["spec_conversation_history"] = app_state[
                "spec_conversation_history"
            ] + [HumanMessage(content=message.content)]
            updated_state["current_step"] = "spec"  # 再度仕様ステップから
            updated_state["next_step"] = ""  # フラグリセット
            await run_graph(updated_state)  # グラフ実行再開
        else:
            await cl.Message(content="予期しないタイミングでのメッセージです。").send()
    # 最初の入力
    elif current_step_logic == "start":
        print("Starting graph execution.")
        initial_state = AppState(
            initial_query=message.content,
            plan_conversation_history=[HumanMessage(content=message.content)],
            plan_output="",
            spec_conversation_history=[],
            spec_output="",
            task_output="",
            issue_output="",
            current_step="planning",  # 最初のステップへ
            next_step="",
            error_message="",
        )
        await run_graph(initial_state)  # グラフ実行を開始
    else:
        await cl.Message(
            content="現在、他の処理を実行中です。完了までお待ちください。"
        ).send()


# --- グラフ実行関数 ---
async def run_graph(initial_state: AppState):
    app = cl.user_session.get("graph_runner")
    if not app:
        await cl.Message(
            content="エラー: グラフ実行インスタンスが見つかりません。"
        ).send()
        return

    final_state = None
    current_step_name = initial_state.get("current_step", "planning")  # 開始ステップ名
    cl.user_session.set("app_state", initial_state)  # 実行開始時の状態を保存

    try:
        # ストリーミング実行
        async for event in app.astream(
            initial_state, {"recursion_limit": 50}
        ):  # 再帰制限を設定
            # print(f"Graph Event: {event}") # デバッグ用
            keys = event.keys()
            if END in keys:
                final_state = event[END]
                print("--- Graph Finished ---")
                break  # グラフ終了
            elif "planning" in keys:
                current_state = event["planning"]
                current_step_name = "planning"
            elif "spec" in keys:
                current_state = event["spec"]
                current_step_name = "spec"
            elif "task" in keys:
                current_state = event["task"]
                current_step_name = "task"
            elif "issue" in keys:
                current_state = event["issue"]
                current_step_name = "issue"
            elif "error_node" in keys:
                # error_node は状態を変更しない想定。直前の状態を取得。
                # LangGraphのastream仕様により入力状態が含まれるか確認が必要。
                # ここではエラー発生前の最後の有効な状態を使う試み。
                final_state = cl.user_session.get("app_state")
                # error_nodeが呼ばれたことを記録（必要なら）
                # final_state["error_message"] = final_state.get(...) # 設定済み
                current_step_name = "error"
                print("--- Graph Finished with Error ---")
                break  # エラー時は即終了
            else:
                # 予期しないイベント
                print(f"Unexpected graph event keys: {keys}")
                # 状態が更新されている可能性があるので取得
                # LangGraphのイベント構造に依存
                if isinstance(event, dict) and len(event) == 1:
                    current_state = list(event.values())[0]
                else:
                    current_state = cl.user_session.get("app_state")  # fallback
                # continue # 処理を続けるか、エラーとするか

            # 状態更新 (UI更新やデバッグ用)
            # print(f"Current State ({current_step_name}): {current_state}")
            cl.user_session.set("app_state", current_state)  # 中間状態を保存

            # ユーザーへの質問が必要な場合、astreamはここで終了する (ENDに遷移するため)
            if current_state.get("next_step") == "ask_user":
                print(f"--- Graph Paused for User Input ({current_step_name}) ---")
                # 質問メッセージは各ステップ内で送信済み
                final_state = current_state  # ユーザー入力待ちの状態を最終状態とする
                break
    except Exception as e:
        print(f"Error during graph execution: {e}")
        import traceback

        traceback.print_exc()  # 詳細なトレースバックを出力
        await cl.Message(content=f"グラフ実行中に予期せぬエラーが発生: {e}").send()
        # エラー発生時の状態を保存しておく
        error_state = cl.user_session.get("app_state", initial_state)
        error_state["error_message"] = str(e)
        final_state = error_state

    # 最終結果の表示など
    if final_state:
        cl.user_session.set("app_state", final_state)  # 最終状態を保存
        if final_state.get("error_message") and current_step_name != "error":
            # error_node以外でエラーメッセージがある場合
            await cl.Message(
                content=f"エラーが発生しました: {final_state['error_message']}"
            ).send()
        elif final_state.get("next_step") == "ask_user":
            # ユーザー入力待ちなので、完了メッセージは出さない
            pass
        elif final_state.get("issue_output"):
            await cl.Message(
                content=f"処理完了。\n\n**Issue詳細:**\n```\n{final_state['issue_output']}\n```"
            ).send()
            # 状態をリセットして次の企画へ
            await cl.Message(content="新しい企画の素案を入力してください。").send()
            # start_chatを呼び出す代わりに状態を直接リセット
            cl.user_session.set(
                "app_state",
                AppState(
                    initial_query="",
                    plan_conversation_history=[],
                    plan_output="",
                    spec_conversation_history=[],
                    spec_output="",
                    task_output="",
                    issue_output="",
                    current_step="start",
                    next_step="",
                    error_message="",
                ),
            )
        elif (
            current_step_name != "error"
            and not final_state.get("next_step") == "ask_user"
        ):
            # ask_userでもなく、issue_outputもなく、エラーノードでもない場合
            # （正常終了だが最終出力がないケース）
            await cl.Message(
                content="処理完了しましたが、最終出力がありません。"
            ).send()
            # 状態リセット
            await cl.Message(content="新しい企画の素案を入力してください。").send()
            cl.user_session.set(
                "app_state",
                AppState(
                    initial_query="",
                    plan_conversation_history=[],
                    plan_output="",
                    spec_conversation_history=[],
                    spec_output="",
                    task_output="",
                    issue_output="",
                    current_step="start",
                    next_step="",
                    error_message="",
                ),
            )


# グラフのコンパイルは on_chat_start で行うため、ここでは不要
# app = workflow.compile()
# cl.user_session.set("graph_runner", app)
