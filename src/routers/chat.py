import json
from chatbot import Chatbot
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from planner import PlannerBot
from tech_spec import TechSpecBot
from issue_generator import IssueGenerator
from models.issue import Issue
from models.models import ChatAndEdit
from models.document import PlanDocument, TechSpecDocument
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
    plan = PlanDocument.find_by_id(chat_and_edit_param.project_id)
    return StreamingResponse(
        process_stream(
            bot,
            chat_and_edit_param.message,
            history=chat_and_edit_param.history if chat_and_edit_param.history else [],
            content=plan.content if plan else "",
        ),
        media_type="application/x-ndjson",
    )


@router.post("/issue/stream")
async def chat_issue_stream(chat_and_edit_param: ChatAndEdit):
    """
    Stream chat responses from IssueGenerator in JSON format (ndjson).
    """
    plan = PlanDocument.find_by_id(chat_and_edit_param.project_id)
    tech_spec = TechSpecDocument.find_by_id(chat_and_edit_param.project_id)

    bot = IssueGenerator(
        plan=plan.content if plan else "",
        tech_spec=tech_spec.content if tech_spec else "",
    )
    issues = Issue.find_by_project_id(chat_and_edit_param.project_id)

    return StreamingResponse(
        process_stream(
            bot,
            chat_and_edit_param.message,
            history=chat_and_edit_param.history if chat_and_edit_param.history else [],
            current_issues=issues,
        ),
        media_type="application/x-ndjson",
    )


@router.post("/tech-spec/stream")
async def chat_tech_spec_stream(chat_and_edit_param: ChatAndEdit):
    """
    Stream chat responses from TechSpecBot in JSON format (ndjson).
    """
    plan = PlanDocument.find_by_id(chat_and_edit_param.project_id)

    bot = TechSpecBot(plan=plan.content if plan else "")
    tech_spec = TechSpecDocument.find_by_id(chat_and_edit_param.project_id)
    return StreamingResponse(
        process_stream(
            bot,
            chat_and_edit_param.message,
            history=chat_and_edit_param.history if chat_and_edit_param.history else [],
            content=tech_spec.content if tech_spec else "",
        ),
        media_type="application/x-ndjson",
    )
