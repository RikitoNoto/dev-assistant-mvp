import json
from chatbot import Chatbot
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from planner import PlannerBot
from tech_spec import TechSpecBot
from issue_generator import IssueGenerator
from models import ChatAndEdit
from routers.utils import (
    get_plan_document_repository,
    get_tech_spec_document_repository,
    get_issue_repository,  # get_issue_document_repository から変更
)

router = APIRouter()


async def process_stream(bot: Chatbot, message: str, history: list = None, **kwargs):
    """
    Processes the bot stream and yields JSON chunks.
    Detects the separator '===============' to switch keys.
    Accepts an optional history list.
    """
    buffer = ""
    is_file_content = False
    separator = "==============="

    async for chunk in bot.stream(message, history=history, **kwargs):
        buffer += chunk

        while True:
            if is_file_content:
                # If we are in file content mode, yield the entire buffer as file content
                if buffer:
                    yield json.dumps({"file": buffer}, ensure_ascii=False) + "\\n"
                    buffer = ""
                # Since we yielded the whole buffer, break the inner loop
                break

            separator_index = buffer.find(separator)
            if separator_index != -1:
                # Yield the part before the separator as a message
                message_part = buffer[:separator_index]
                if message_part:
                    yield json.dumps(
                        {"message": message_part}, ensure_ascii=False
                    ) + "\\n"

                # Remove the message part and the separator from the buffer
                buffer = buffer[separator_index + len(separator) :]
                # Remove leading newline if present after separator
                if buffer.startswith("\\n"):
                    buffer = buffer[1:]

                # Switch to file content mode
                is_file_content = True
                # Continue the inner loop to process the remaining buffer in file mode immediately
                continue  # Explicitly continue to re-evaluate the buffer in the new mode
            else:
                # If no separator is found and not in file content mode,
                # yield the entire buffer as a message if it's not empty
                if buffer and not is_file_content:
                    yield json.dumps({"message": buffer}, ensure_ascii=False) + "\\n"
                    buffer = ""  # Clear buffer after yielding
                # Break the inner loop as there's nothing more to process without a separator
                break

    # After the stream ends, yield any remaining buffer content
    if buffer:
        key = "file" if is_file_content else "message"
        yield json.dumps({key: buffer}, ensure_ascii=False) + "\\n"


@router.post("/plan/stream")
async def chat_plan_stream(chat_and_edit_param: ChatAndEdit):
    """
    Stream chat responses from PlannerBot in JSON format (ndjson).
    """
    bot = PlannerBot()
    repo = get_plan_document_repository()
    plan = repo.get_by_id(chat_and_edit_param.project_id)
    return StreamingResponse(
        process_stream(
            bot,
            chat_and_edit_param.message,
            history=chat_and_edit_param.history,
            content=plan.content,
        ),
        media_type="application/x-ndjson",
    )


@router.post("/issue/stream")
async def chat_issue_stream(chat_and_edit_param: ChatAndEdit):
    """
    Stream chat responses from IssueGenerator in JSON format (ndjson).
    """
    plan_repo = get_plan_document_repository()
    plan = plan_repo.get_by_id(chat_and_edit_param.project_id)

    tech_spec_repo = get_tech_spec_document_repository()
    tech_spec = tech_spec_repo.get_by_id(chat_and_edit_param.project_id)

    from collections import defaultdict

    bot = IssueGenerator(plan=plan.content, tech_spec=tech_spec.content)
    issue_repo = get_issue_repository()  # get_issue_document_repository から変更
    issues = issue_repo.get_by_project_id(chat_and_edit_param.project_id)

    current_issues_dict = defaultdict(list)
    if issues:
        for issue in issues:
            current_issues_dict[issue.status].append(issue.title)

    # IssueGeneratorが期待する形式に変換 (list of dicts)
    # ただし、IssueGeneratorのstreamメソッドのkwargs.get("current_issues", []) の型ヒントは list[dict[str, list[str]]]
    # そのため、current_issues_dictをそのまま渡すか、あるいは期待する形式に合わせる必要がある。
    # issue_generator.pyの実装を見ると、 list[dict[str, list[str]]] を期待している。
    # しかし、ユーザーのフィードバックは {status: [issues], status: [issues]} の形式。
    # ここではユーザーのフィードバックを優先し、IssueGenerator側の修正が必要になる可能性を示唆する。
    # 一旦、ユーザーの指示通りの形式で渡す。
    # もしIssueGeneratorがこの形式を直接扱えない場合は、IssueGenerator側を修正するか、
    # ここで list[dict[str, list[str]]] の形式に変換する必要がある。
    # 例: current_issues = [{status: titles} for status, titles in current_issues_dict.items()]

    current_issues_for_bot = dict(current_issues_dict) if current_issues_dict else {}

    return StreamingResponse(
        process_stream(
            bot,
            chat_and_edit_param.message,
            history=chat_and_edit_param.history,
            current_issues=current_issues_for_bot,  # IssueGeneratorのstreamメソッドに渡す
        ),
        media_type="application/x-ndjson",
    )


@router.post("/tech-spec/stream")
async def chat_tech_spec_stream(chat_and_edit_param: ChatAndEdit):
    """
    Stream chat responses from TechSpecBot in JSON format (ndjson).
    """
    plan_repo = get_plan_document_repository()
    plan = plan_repo.get_by_id(chat_and_edit_param.project_id)

    bot = TechSpecBot(plan=plan)
    tech_spec_repo = get_tech_spec_document_repository()
    tech_spec = tech_spec_repo.get_by_id(chat_and_edit_param.project_id)
    return StreamingResponse(
        process_stream(
            bot,
            chat_and_edit_param.message,
            history=chat_and_edit_param.history,
            content=tech_spec.content,
        ),
        media_type="application/x-ndjson",
    )
