import os
import chainlit as cl
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langgraph.graph import StateGraph, END
from typing import (
    TypedDict,
    Annotated,
    List,
    Optional,
    Dict,
    Any,
)

# import requests # requestsは不要になった
from dotenv import load_dotenv
import json
import httpx
from github_client import GitHubClient

# .envファイルから環境変数を読み込む
load_dotenv()

# --- Dify API Keys ---
PLANNING_APP_API_KEY = os.getenv("PLANNING_APP_API_KEY")
SPEC_APP_API_KEY = os.getenv("SPEC_APP_API_KEY")
TASK_APP_API_KEY = os.getenv("TASK_APP_API_KEY")
ISSUE_APP_API_KEY = os.getenv("ISSUE_APP_API_KEY")

# --- GitHub Settings ---
GITHUB_PAT = os.getenv("GITHUB_PAT")
GITHUB_OWNER = os.getenv("GITHUB_OWNER")
GITHUB_REPO = os.getenv("GITHUB_REPO")
GITHUB_PROJECT_NUMBER_STR = os.getenv("GITHUB_PROJECT_NUMBER")
GITHUB_PROJECT_NUMBER = None
if GITHUB_PROJECT_NUMBER_STR:
    try:
        GITHUB_PROJECT_NUMBER = int(GITHUB_PROJECT_NUMBER_STR)
    except ValueError:
        print("Warning: GITHUB_PROJECT_NUMBER is not a valid integer.")

# --- API Endpoints ---
DIFY_API_ENDPOINT = "http://localhost/v1/chat-messages"


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
    issue_output: List[Dict[str, str]]  # Issue辞書のリスト
    github_project_id: Optional[str]  # GitHub Project V2 の Node ID
    created_issues: List[Dict[str, Any]]  # 作成されたIssueの情報リスト
    current_step: str  # 現在の処理ステップ
    next_step: str  # 次の処理ステップ or ユーザーへの質問フラグ
    error_message: Optional[str]  # エラーメッセージ (Optionalに変更)


# --- Dify API呼び出し関数 ---
async def call_dify_api(
    api_key: str,
    query: str,
    conversation_id: str = "",
    inputs: Optional[Dict[str, Any]] = None,  # inputsをOptionalに
    history: Optional[List[BaseMessage]] = None,  # historyをOptionalに
    user: str = "chainlit-user",
) -> Dict[str, Any]:  # 戻り値の型ヒントを修正
    """Dify APIを呼び出す共通関数 (ストリーミング対応)"""
    if not api_key:
        return {
            "answer": "",
            "conversation_id": conversation_id,
            "error": "API key is missing.",
        }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload: Dict[str, Any] = {  # payloadの型ヒント
        "inputs": inputs if inputs else {},
        "query": query,
        "response_mode": "streaming",
        "conversation_id": conversation_id,  # 空文字でもOK
        "user": user,
        "files": [],
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
    inputs: Dict[str, Any],  # inputsの型ヒント
    user: str = "chainlit-user",
) -> Dict[str, Any]:  # 戻り値の型ヒントを修正
    """Dify Completion APIを呼び出す関数 (ストリーミング対応)"""
    if not api_key:
        return {"answer": "", "error": "API key is missing."}

    COMPLETION_API_ENDPOINT = "http://localhost/v1/completion-messages"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload: Dict[str, Any] = {  # payloadの型ヒント
        "inputs": inputs,
        "response_mode": "streaming",
        "user": user,
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


async def github_publish_step(
    state: AppState,
) -> Dict[str, Any]:  # 戻り値の型ヒント修正
    """生成されたIssueをGitHubに発行し、プロジェクトに追加するステップ"""
    print("--- GitHub Publish Step ---")
    await cl.Message(content="GitHubへのIssue発行とプロジェクト追加を実行中...").send()

    github_client: Optional[GitHubClient] = cl.user_session.get("github_client")
    # issue_output は List[Dict[str, str]] 型のはず
    issues_to_create: List[Dict[str, str]] = state.get("issue_output", [])
    project_id: Optional[str] = state.get("github_project_id")
    created_issues_list: List[Dict[str, Any]] = []
    errors: List[str] = []

    if not github_client:
        return {
            **state,
            "error_message": "GitHubクライアントが初期化されていません。",
            "next_step": "error",
        }

    if not issues_to_create:
        await cl.Message(content="発行対象のIssueがありません。").send()
        # issue_outputが空でもcreated_issuesは空リストで返す
        return {
            **state,
            "created_issues": [],
            "current_step": "github_publish",
            "next_step": "end",
        }

    # プロジェクトIDが未取得であれば取得を試みる
    if not project_id and GITHUB_PROJECT_NUMBER is not None:
        try:
            project_id = await github_client.get_project_v2_id(GITHUB_PROJECT_NUMBER)
            if not project_id:
                error_msg = (
                    f"GitHub Project V2 (Number: {GITHUB_PROJECT_NUMBER}) "
                    f"が見つかりません。Issueは作成されますが、プロジェクトには追加されません。"
                )
                errors.append(error_msg)
                await cl.Message(content=error_msg).send()
            else:
                cl.user_session.set(
                    "github_project_id", project_id
                )  # セッション経由で更新
                print(f"Fetched GitHub Project ID: {project_id}")

        except Exception as e:
            error_msg = f"GitHubプロジェクトID取得中にエラー: {e}"
            print(error_msg)
            errors.append(
                error_msg + " Issueは作成されますが、プロジェクトには追加されません。"
            )
            await cl.Message(content=errors[-1]).send()
            project_id = None
    elif project_id:
        # 既に取得済みの場合はセッションから取得し直す（状態遷移で渡ってこない場合のため）
        project_id = cl.user_session.get("github_project_id")

    # Issueを作成し、プロジェクトに追加
    for issue_data in issues_to_create:
        title = issue_data.get("title", "タイトルなし")
        body = issue_data.get("body", "")
        try:
            created_issue = await github_client.create_issue(title=title, body=body)
            created_issues_list.append(created_issue)  # 作成成功したIssue情報を追加
            issue_node_id = created_issue.get("node_id")
            issue_number = created_issue.get("number")
            issue_url = created_issue.get("html_url", "#")
            await cl.Message(
                content=f"Issue #{issue_number} を作成しました: {issue_url}"
            ).send()

            if project_id and issue_node_id:
                item_id = await github_client.add_issue_to_project_v2(
                    project_id, issue_node_id
                )
                # item_id が取得できた場合のみメッセージ表示
                if item_id:
                    await cl.Message(
                        content=f"Issue #{issue_number} をプロジェクトに追加しました。"
                    ).send()
                else:  # item_id が取得できなかった場合 (add_issue_to_project_v2 が None を返した場合など)
                    error_msg = (
                        f"Issue #{issue_number} のプロジェクト追加に失敗しました。"
                    )
                    errors.append(error_msg)
                    await cl.Message(content=error_msg).send()
            elif project_id and not issue_node_id:  # Issue Node ID がない場合
                error_msg = (
                    f"Issue #{issue_number} のNode IDが取得できず、"
                    "プロジェクトに追加できませんでした。"
                )
                errors.append(error_msg)
                await cl.Message(content=error_msg).send()
            # else: project_id がない場合は、そもそもこの if project_id and issue_node_id: ブロックに入らない

        except Exception as e:
            error_msg = f"Issue '{title}' の作成またはプロジェクト追加中にエラー: {e}"
            print(error_msg)
            errors.append(error_msg)
            await cl.Message(content=error_msg).send()
            # 1つのIssueでエラーが起きても、他のIssueの処理は続ける

    final_error_message = "\n".join(errors) if errors else None

    # 状態を返す前にcreated_issuesを更新
    # state["created_issues"] = created_issues_list # 直接変更はしない

    # 戻り値は更新するフィールドのみを含む辞書
    return {
        "created_issues": created_issues_list,
        "github_project_id": project_id,
        "error_message": final_error_message,
        "current_step": "github_publish",
        "next_step": "end" if not final_error_message else "error",
    }


async def planning_step(state: AppState) -> Dict[str, Any]:  # 戻り値の型ヒント修正
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

    if response.get("error"):  # errorキーが存在するか確認
        return {"error_message": response["error"], "next_step": "error"}

    ai_response_text = response.get("answer", "")  # answerがない場合も考慮
    new_conversation_id = response.get(
        "conversation_id", conversation_id
    )  # IDがない場合は維持

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
        # 戻り値は更新するフィールドのみ
        return {
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
            "plan_conversation_history": updated_history,
            "current_step": "planning",
            "next_step": "ask_user",
        }
    else:
        print(f"Unexpected response from planning app: {ai_response_text}")
        await cl.Message(
            content=f"企画アプリから予期しない応答がありました:\n{ai_response_text}\n処理を継続します。"
        ).send()
        # 想定外でも企画書として扱う
        return {
            "plan_conversation_history": updated_history,
            "plan_output": ai_response_text,  # そのまま出力
            "current_step": "planning",
            "next_step": "spec",  # 次のステップへ
        }


async def spec_step(state: AppState) -> Dict[str, Any]:  # 戻り値の型ヒント修正
    """技術仕様書作成ステップ"""
    print("--- Spec Step ---")
    await cl.Message(content="技術仕様書作成アプリを実行中...").send()
    current_history = state.get("spec_conversation_history", [])
    plan_output = state.get("plan_output", "")

    if not plan_output:
        return {"error_message": "企画書が見つかりません。", "next_step": "error"}

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

    if response.get("error"):
        return {"error_message": response["error"], "next_step": "error"}

    ai_response_text = response.get("answer", "")
    new_conversation_id = response.get("conversation_id", conversation_id)

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
            "spec_conversation_history": updated_history,
            "current_step": "spec",
            "next_step": "ask_user",
        }
    else:
        print(f"Unexpected response from spec app: {ai_response_text}")
        await cl.Message(
            content=f"技術仕様アプリから予期しない応答がありました:\n{ai_response_text}\n処理を継続します。"
        ).send()
        # 想定外でも仕様書として扱う
        return {
            "spec_conversation_history": updated_history,
            "spec_output": ai_response_text,  # そのまま出力
            "current_step": "spec",
            "next_step": "task",  # 次のステップへ
        }


async def task_step(state: AppState) -> Dict[str, Any]:  # 戻り値の型ヒント修正
    """タスク分解ステップ"""
    print("--- Task Step ---")
    await cl.Message(content="タスク分解アプリを実行中...").send()
    plan_output = state.get("plan_output", "")
    spec_output = state.get("spec_output", "")

    if not plan_output or not spec_output:
        return {
            "error_message": "企画書または技術仕様書が見つかりません。",
            "next_step": "error",
        }

    # Dify Completion API呼び出し (inputsを使用)
    # query は inputs に含めるか、API側で解釈する想定
    inputs = {"plan": plan_output, "tech_spec": spec_output}
    # 必要であれば固定の指示を inputs に追加
    # inputs["instruction"] = "企画書と技術仕様書からタスクを分解してください。"

    response = await call_completion_api(TASK_APP_API_KEY, inputs=inputs)

    if response.get("error"):
        return {"error_message": response["error"], "next_step": "error"}

    task_output_str = response.get("answer", "")  # answerがない場合も考慮
    print(f"Task decomposition finished. Output:\n{task_output_str}")
    await cl.Message(
        content=f"タスク分解が完了しました。\n```\n{task_output_str}\n```"
    ).send()

    return {
        "task_output": task_output_str,
        "current_step": "task",
        "next_step": "issue",
    }


async def issue_step(state: AppState) -> Dict[str, Any]:  # 戻り値の型ヒント修正
    """Issue出力ステップ"""
    print("--- Issue Step ---")
    await cl.Message(content="Issue出力アプリを実行中...").send()
    plan_output = state.get("plan_output", "")
    spec_output = state.get("spec_output", "")
    task_output = state.get("task_output", "")

    if not task_output:
        return {"error_message": "タスクリストが見つかりません。", "next_step": "error"}

    # Dify Completion API呼び出しのための準備 (inputsはループ内で生成)

    try:
        task_list_data = json.loads(task_output)
        # "issues" キーが存在し、それがリストであることを確認
        if (
            isinstance(task_list_data, dict)
            and "issues" in task_list_data
            and isinstance(task_list_data["issues"], list)
        ):
            tasks = task_list_data["issues"]
        else:
            # 想定外の形式の場合、task_output全体を単一タスクとして扱うか、エラーにする
            # ここではエラーとする
            print(f"Error: Unexpected format in task_output: {task_output}")
            return {
                "error_message": "タスク分解アプリの出力形式が不正です。",
                "next_step": "error",
            }
    except json.JSONDecodeError:
        print(f"Error: Failed to decode task_output JSON: {task_output}")
        return {
            "error_message": "タスク分解アプリの出力(JSON)の解析に失敗しました。",
            "next_step": "error",
        }

    issues: List[Dict[str, str]] = []  # Issue情報を格納するリスト (辞書形式)
    for task_title in tasks:
        # task_title が文字列であることを念のため確認
        if not isinstance(task_title, str):
            print(f"Warning: Skipping non-string task item: {task_title}")
            continue

        # Issue本文生成のためのAPI呼び出し
        response = await call_completion_api(
            ISSUE_APP_API_KEY,
            inputs={  # inputs を毎回生成
                "plan": plan_output,
                "tech_spec": spec_output,
                "tasks": task_output,  # 元のタスクリスト全体もコンテキストとして渡す
                "title": task_title,  # 現在処理中のタスクタイトル
            },
        )

        if response.get("error"):
            # 1つのIssue生成エラーで全体をエラーとする
            return {
                "error_message": f"Issue本文生成中にエラー: {response['error']}",
                "next_step": "error",
            }

        issue_body = response.get("answer", "")  # answerがない場合も考慮
        issues.append({"title": task_title, "body": issue_body})
        print(f"Issue generated for '{task_title}'. Body:\n{issue_body[:100]}...")

    print(f"Generated {len(issues)} issues.")

    # 完了メッセージは run_graph 関数で表示 (GitHub発行後)

    return {
        "issue_output": issues,
        "current_step": "issue",
        "next_step": "github_publish",
    }


# --- 条件分岐ロジック ---
def should_continue_or_ask(state: Dict[str, Any]) -> str:  # stateの型ヒントをDictに
    """企画/仕様ステップ後、継続するかユーザーに質問するかを判断"""
    next_step = state.get("next_step", "")  # next_stepがない場合も考慮
    error_message = state.get("error_message")

    if error_message:
        print(f"Decision: Error ({error_message})")
        return "error"
    elif next_step == "ask_user":
        print("Decision: Ask User")
        return "ask_user"
    elif next_step == "spec":
        print("Decision: Continue to Spec")
        return "spec"  # 仕様ステップへ
    elif next_step == "task":
        print("Decision: Continue to Task")
        return "task"  # タスク分解ステップへ
    elif next_step == "issue":
        print("Decision: Continue to Issue")
        return "issue"  # Issue出力ステップへ
    elif next_step == "github_publish":
        print("Decision: Continue to GitHub Publish")
        return "github_publish"  # GitHub発行ステップへ
    elif next_step == "end":
        print("Decision: End")
        return END  # 終了
    else:
        print(f"Decision: Error (Unknown next step: '{next_step}')")
        # 不明な場合はエラーとする
        return "error"


# --- LangGraphグラフ構築 ---
# AppStateではなくDict[str, Any]を使用する方がLangGraphの挙動と整合性が取れる場合がある
workflow = StateGraph(AppState)  # AppStateを使用するように変更
# workflow = StateGraph(Dict[str, Any]) # 元のコードをコメントアウト

# ノードを追加
workflow.add_node("planning", planning_step)
workflow.add_node("spec", spec_step)
workflow.add_node("task", task_step)
workflow.add_node("issue", issue_step)
workflow.add_node("github_publish", github_publish_step)  # GitHub発行ノード追加
# error_node はエラーメッセージをコンソールに出力し、状態をそのまま返す
workflow.add_node(
    "error_node",
    lambda state: print(
        f"Error Node Triggered: {state.get('error_message', 'Unknown error')}"
    ),
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
# issue ステップ後は github_publish ステップへ
workflow.add_conditional_edges(
    "issue",
    should_continue_or_ask,  # next_stepを見て判断
    {"github_publish": "github_publish", "error": "error_node"},
)
# github_publish ステップ後は終了またはエラー
workflow.add_conditional_edges(
    "github_publish",
    should_continue_or_ask,  # next_stepを見て判断 (end or error)
    {END: END, "error": "error_node"},
)
# エラーノードからは終了
workflow.add_edge("error_node", END)


# --- Chainlit UI ---
@cl.on_chat_start
async def start_chat():
    # --- GitHub Client Initialization ---
    github_client = None
    github_error = None
    missing_vars = []
    if not GITHUB_PAT:
        missing_vars.append("GITHUB_PAT")
    if not GITHUB_OWNER:
        missing_vars.append("GITHUB_OWNER")
    if not GITHUB_REPO:
        missing_vars.append("GITHUB_REPO")
    # GITHUB_PROJECT_NUMBER は必須ではない

    if not missing_vars:
        try:
            github_client = GitHubClient(
                token=GITHUB_PAT, owner=GITHUB_OWNER, repo=GITHUB_REPO
            )
            cl.user_session.set("github_client", github_client)
            print("GitHub client initialized successfully.")
            # 初期状態でプロジェクトIDを取得しておく
            if GITHUB_PROJECT_NUMBER is not None:
                print(
                    f"Attempting to pre-fetch Project ID for project number {GITHUB_PROJECT_NUMBER}"
                )
                project_id = await github_client.get_project_v2_id(
                    GITHUB_PROJECT_NUMBER
                )
                if project_id:
                    cl.user_session.set("github_project_id", project_id)
                    print(f"Pre-fetched Project ID: {project_id}")
                else:
                    # IDが見つからない場合もエラーとはしない（publishステップで再試行）
                    print(
                        f"Could not pre-fetch Project ID for project number {GITHUB_PROJECT_NUMBER}."
                    )
        except ValueError as e:  # 初期化時の必須引数チェックエラー
            github_error = f"GitHubクライアント初期化エラー: {e}"
            print(github_error)
        except Exception as e:  # APIアクセス中の予期せぬエラー
            github_error = (
                f"GitHubクライアント初期化・プロジェクトID取得中に予期せぬエラー: {e}"
            )
            print(github_error)
    else:
        github_error = (
            f"GitHub連携に必要な環境変数が不足しています: {', '.join(missing_vars)}"
        )
        print(github_error)

    # --- Graph Compilation ---
    if cl.user_session.get("graph_runner") is None:
        try:
            app = workflow.compile()
            cl.user_session.set("graph_runner", app)
            print("Graph compiled successfully.")
        except Exception as e:
            print(f"Error compiling graph: {e}")
            await cl.Message(content=f"グラフのコンパイルエラー: {e}").send()
            return

    # --- Initial State Setup ---
    # AppStateではなくDictとして初期化する方が安全かもしれない
    initial_state: Dict[str, Any] = {
        "initial_query": "",
        "plan_conversation_history": [],
        "plan_output": "",
        "spec_conversation_history": [],
        "spec_output": "",
        "task_output": "",
        "issue_output": [],
        "github_project_id": cl.user_session.get("github_project_id"),
        "created_issues": [],
        "current_step": "start",
        "next_step": "",
        "error_message": github_error,
    }
    cl.user_session.set("app_state", initial_state)

    # --- Initial Message ---
    if github_error:
        await cl.Message(
            content=f"警告: {github_error} GitHub連携機能は無効になります。"
        ).send()
    await cl.Message(content="企画の素案を入力してください。").send()


@cl.on_message
async def main(message: cl.Message):
    app_state: Dict[str, Any] = cl.user_session.get(
        "app_state", {}
    )  # 存在しない場合も考慮
    graph_runner = cl.user_session.get("graph_runner")

    if not graph_runner:
        await cl.Message(content="アプリ初期化失敗: グラフ未コンパイル").send()
        return

    current_step_logic = app_state.get("current_step", "start")
    next_step_flag = app_state.get("next_step", "")

    # ユーザー入力が必要な状態 ("ask_user")
    if next_step_flag == "ask_user":
        # 状態をコピーして更新するのではなく、必要な情報だけを渡してグラフを再開
        resume_state: Dict[str, Any] = {}
        if current_step_logic == "planning":
            print("User responded to planning question.")
            # 既存の履歴にユーザーメッセージを追加
            history = app_state.get("plan_conversation_history", [])
            resume_state = {
                "plan_conversation_history": history
                + [HumanMessage(content=message.content)]
            }
            # 再開ポイントは planning ノード
            await run_graph(resume_state, resume_from="planning")
        elif current_step_logic == "spec":
            print("User responded to spec question.")
            history = app_state.get("spec_conversation_history", [])
            resume_state = {
                "spec_conversation_history": history
                + [HumanMessage(content=message.content)]
            }
            # 再開ポイントは spec ノード
            await run_graph(resume_state, resume_from="spec")
        else:
            # 予期しないステップで ask_user フラグが立っている場合
            await cl.Message(content="予期しないタイミングでのメッセージです。").send()

    # 最初の入力 ("start" 状態)
    elif current_step_logic == "start":
        print("Starting graph execution.")
        # start_chatで設定された初期状態をベースに、最初のクエリを追加
        initial_state_from_session = cl.user_session.get("app_state", {})
        start_state: Dict[str, Any] = {
            **initial_state_from_session,  # セッションの状態を引き継ぐ
            "initial_query": message.content,
            "plan_conversation_history": [HumanMessage(content=message.content)],
            # 他のフィールドは initial_state_from_session から引き継がれる
        }
        await run_graph(start_state)  # 最初から実行
    # グラフ実行中の場合
    elif current_step_logic != "start" and next_step_flag != "ask_user":
        await cl.Message(
            content="現在、他の処理を実行中です。完了までお待ちください。"
        ).send()
    # 上記以外 (ask_userでもstartでもなく、実行中でもない) は基本的に到達しないはずだが、
    # 到達した場合に備えてメッセージを出すか、何もしないか。ここでは何もしない。
    # else:
    #     print(f"Unexpected state in main: current_step={current_step_logic}, next_step={next_step_flag}")
    #     await cl.Message(content="予期しない状態です。").send()


# --- グラフ実行関数 ---
async def run_graph(input_state: Dict[str, Any], resume_from: Optional[str] = None):
    """LangGraphを実行し、状態を更新する"""
    app = cl.user_session.get("graph_runner")
    if not app:
        await cl.Message(
            content="エラー: グラフ実行インスタンスが見つかりません。"
        ).send()
        return

    # 現在のセッション状態を取得し、入力状態で更新
    current_session_state = cl.user_session.get("app_state", {})
    merged_state = {**current_session_state, **input_state}

    # 再開ポイントが指定されている場合は、そのノードから実行を開始
    # LangGraphのastreamは再開ポイントを直接指定できないため、
    # 実行するノードを制御するロジックが必要になる場合がある。
    # ここでは、input_stateに必要な情報が含まれていると仮定し、
    # グラフ全体を再実行するが、条件分岐で適切なパスに進むことを期待する。
    # (より高度な制御が必要な場合は、Graph.streamのcheckpointerなどを使う)

    final_state = None
    current_step_name = merged_state.get(
        "current_step", "planning"
    )  # デフォルトはplanning

    try:
        async for event in app.astream(merged_state, {"recursion_limit": 50}):
            keys = event.keys()
            # print(f"Graph Event Keys: {keys}") # デバッグ用

            # イベントから最新の状態を取得
            # イベントのキーは実行されたノード名
            if END in keys:
                final_state = event[END]
                print("--- Graph Finished ---")
                break
            elif "error_node" in keys:
                # エラーノードが呼ばれた場合、その時点の状態を最終状態とする
                # error_node自体は状態を変更しない想定
                final_state = merged_state  # エラー発生直前の状態
                final_state["error_message"] = final_state.get(
                    "error_message", "Unknown error from error_node"
                )
                current_step_name = "error"
                print(
                    f"--- Graph Finished with Error ({final_state['error_message']}) ---"
                )
                break
            else:
                # 通常のノード実行の場合、イベント辞書から状態を取得
                # イベント辞書のキーは一つのはず (実行されたノード名)
                if len(keys) == 1:
                    node_name = list(keys)[0]
                    current_step_name = node_name
                    # イベントの値が更新された状態
                    updated_fields = event[node_name]
                    # 現在のセッション状態にマージ
                    merged_state = {**merged_state, **updated_fields}
                    # print(f"State updated by node '{node_name}': {updated_fields}") # デバッグ用
                else:
                    # 予期しないイベント形式
                    print(f"Warning: Unexpected graph event structure: {event}")
                    # とりあえず最後の状態を使う
                    final_state = merged_state
                    break

            # 更新された状態をセッションに保存
            cl.user_session.set("app_state", merged_state)

            # ユーザー入力待ちで中断する場合
            if merged_state.get("next_step") == "ask_user":
                print(f"--- Graph Paused for User Input ({current_step_name}) ---")
                final_state = merged_state  # 中断時の状態を最終状態とする
                break

    except Exception as e:
        print(f"Error during graph execution: {e}")
        import traceback

        traceback.print_exc()
        await cl.Message(content=f"グラフ実行中に予期せぬエラーが発生: {e}").send()
        # エラー発生時の状態を保存
        error_state = cl.user_session.get("app_state", {})
        error_state["error_message"] = str(e)
        final_state = error_state

    # --- 最終結果の処理 ---
    if final_state:
        # 最終状態をセッションに保存
        cl.user_session.set("app_state", final_state)

        error_msg = final_state.get("error_message")
        next_step = final_state.get("next_step")

        if error_msg and current_step_name != "error":
            # error_node以外でエラーメッセージがある場合
            await cl.Message(content=f"エラーが発生しました: {error_msg}").send()
            # エラー発生後もリセットしてよいか、要検討。一旦リセットする。
            await reset_chat_state()

        elif next_step == "ask_user":
            # ユーザー入力待ちなので完了メッセージは表示しない
            pass

        elif current_step_name == "github_publish" and not error_msg:
            # GitHub発行ステップが正常終了した場合
            created_issues_info = final_state.get("created_issues", [])
            result_message = ""
            if created_issues_info:
                issue_links = [
                    f"- [Issue #{i.get('number')}]({i.get('html_url')})"
                    for i in created_issues_info
                    if i.get("number") and i.get("html_url")
                ]
                result_message = (
                    "処理完了。以下のIssueがGitHubに作成されました:\n"
                    + "\n".join(issue_links)
                )
                if (
                    cl.user_session.get("github_project_id")
                    and GITHUB_PROJECT_NUMBER is not None
                ):
                    result_message += f"\nIssueはプロジェクト #{GITHUB_PROJECT_NUMBER} に追加されました（一部失敗している可能性あり）。"
            else:
                result_message = "処理完了。Issueは作成されませんでした。"

            await cl.Message(content=result_message).send()
            await reset_chat_state()  # 正常完了後リセット

        elif current_step_name == "error":
            # error_node に到達した場合 (エラーメッセージは上で表示済み)
            await reset_chat_state()  # エラー後リセット

        elif next_step == END and not error_msg:
            # github_publish を経由せずに正常終了した場合 (例: Issueがなかった、またはGitHub連携なし)
            # この条件は github_publish 成功時の後にも評価される可能性があるため、
            # current_step_name で区別するか、より明確な完了フラグが必要かもしれない。
            # ここでは github_publish 以外での正常終了とみなす。
            if current_step_name != "github_publish":
                await cl.Message(content="処理は正常に完了しました。").send()
                await reset_chat_state()
            # github_publish 成功時は既にメッセージ表示とリセット済みなので何もしない

        # 上記以外のケース (エラーでもask_userでもなく、正常完了でもない)
        elif current_step_name != "error" and next_step != "ask_user":
            await cl.Message(
                content="処理は完了しましたが、予期しない状態です。"
            ).send()
            await reset_chat_state()
        # else: # error でも ask_user でもなく、next_step が END でもない場合 (通常は到達しない)
        #     print(f"Unhandled final state: current_step={current_step_name}, next_step={next_step}, error={error_msg}")


async def reset_chat_state():
    """チャットの状態をリセットし、次の入力を促す"""
    await cl.Message(content="新しい企画の素案を入力してください。").send()
    # GitHubクライアントとプロジェクトIDは維持
    github_project_id = cl.user_session.get("github_project_id")
    # AppStateではなくDictとして初期化
    cl.user_session.set(
        "app_state",
        {
            "initial_query": "",
            "plan_conversation_history": [],
            "plan_output": "",
            "spec_conversation_history": [],
            "spec_output": "",
            "task_output": "",
            "issue_output": [],
            "github_project_id": github_project_id,  # 維持
            "created_issues": [],
            "current_step": "start",
            "next_step": "",
            "error_message": None,  # エラーリセット
        },  # 閉じ括弧を追加
    )


# グラフのコンパイルは on_chat_start で行う
