import json
import logging
import os
from chatbot import Chatbot
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from issue_generator import IssueTitleGenerator, IssueContentGenerator
from models.issue import Issue
from models.models import ChatAndEdit
from models.document import PlanDocument, TechSpecDocument
from models.project import Project
from planner import PlannerBot
from routers.issues import get_github_repository
from routers.utils import DEBUG
from tech_spec import TechSpecBot
from repositories.issues.github import GitHubIssuesRepository

router = APIRouter()

logger = logging.getLogger("uvicorn")

async def process_stream(bot: Chatbot, message: str, history: list = None, **kwargs):
    """
    Processes the bot stream and yields JSON chunks.
    Detects the separator '===============' to switch keys.
    Accepts an optional history list.
    """
    if DEBUG:
        logger.info(f"Processing stream with message: {message}")
    all_chunks: list[str] = []
    buffer = ""
    is_file_content = False
    separator = "==============="

    async for chunk in bot.stream(message, history=history, **kwargs):
        buffer += chunk
        all_chunks.append(chunk)

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
    
    if DEBUG:
        logger.info(f"Output: {''.join(all_chunks)}")

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


@router.post("/issue-titles/stream")
async def chat_issue_titles_stream(chat_and_edit_param: ChatAndEdit):
    """
    Stream chat responses from IssueTitleGenerator in JSON format (ndjson).
    """
    plan = PlanDocument.find_by_id(chat_and_edit_param.project_id)
    tech_spec = TechSpecDocument.find_by_id(chat_and_edit_param.project_id)

    bot = IssueTitleGenerator(
        plan=plan.content if plan else "",
        tech_spec=tech_spec.content if tech_spec else "",
    )
    issues = Issue.find_by_project_id(chat_and_edit_param.project_id)
        
    project = Project.find_by_id(chat_and_edit_param.project_id)
    github_issues = []
    
    if project and project.github_project_id:
        # Project has GitHub integration, fetch GitHub issues
        try:
            github_repo = get_github_repository()
            github_issues = [
                Issue(
                    issue_id=issue.id,
                    project_id=chat_and_edit_param.project_id,
                    title=issue.title,
                    description=issue.description,
                    status=issue.status,
                    created_at=issue.created_at,
                    updated_at=issue.updated_at,
                )
                for issue in github_repo.fetch_issues(project_id=project.github_project_id)
            ]
        except Exception as e:
            print(f"Error fetching GitHub issues: {str(e)}")
    
    # Combine local and GitHub issues
    all_issues = issues + github_issues

    return StreamingResponse(
        process_stream(
            bot,
            chat_and_edit_param.message,
            history=chat_and_edit_param.history if chat_and_edit_param.history else [],
            current_issues=all_issues,
        ),
        media_type="application/x-ndjson",
    )


@router.post("/issue-content/{issue_id}/stream")
async def generate_issue_content_stream(issue_id: str, chat_and_edit_param: ChatAndEdit):
    """
    Stream issue content generation responses from IssueContentGenerator in JSON format (ndjson).
    
    Args:
        issue_id: The ID of the issue to generate content for
        chat_and_edit_param: ChatAndEdit containing project_id, issue_title, message, and optional chat history
        
    Returns:
        StreamingResponse: A streaming response containing the generated issue content
    """
    issue = Issue.find_by_id(chat_and_edit_param.project_id, issue_id)
    if issue is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Issue with ID '{issue_id}' not found."
        )
    
    # Get plan and tech spec documents for the project
    plan = PlanDocument.find_by_id(issue.project_id)
    tech_spec = TechSpecDocument.find_by_id(issue.project_id)
    
    # Initialize the IssueContentGenerator with plan and tech spec
    content_generator = IssueContentGenerator(
        plan=plan.content if plan else "",
        tech_spec=tech_spec.content if tech_spec else "",
    )
    
    # Return a streaming response
    return StreamingResponse(
        process_stream(
            content_generator,
            chat_and_edit_param.message,
            history=chat_and_edit_param.history if chat_and_edit_param.history else [],
            issue_title=issue.title,
            issue_str=issue.description,
        ),
        media_type="application/x-ndjson",
    )


@router.post("/issue-content/github/{issue_id}/stream")
async def generate_github_issue_content_stream(issue_id: str, chat_and_edit_param: ChatAndEdit):
    """
    Stream GitHub issue content generation responses from IssueContentGenerator in JSON format (ndjson).
    
    Args:
        issue_id: The ID of the GitHub issue to generate content for
        chat_and_edit_param: ChatAndEdit containing project_id, message, and optional chat history
        
    Returns:
        StreamingResponse: A streaming response containing the generated issue content
    """
    # Get GitHub token from environment
    github_token = os.environ.get("GITHUB_TOKEN")
    if not github_token:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GitHub token not configured."
        )
    
    # Initialize GitHub repository
    github_repo = GitHubIssuesRepository(github_token)
    
    try:
        # Get GitHub issue using the find_by_id method
        issue = github_repo.find_by_id(issue_id)
        if issue is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"GitHub issue with ID '{issue_id}' not found."
            )
        
        # Get plan and tech spec documents for the project
        plan = PlanDocument.find_by_id(chat_and_edit_param.project_id)
        tech_spec = TechSpecDocument.find_by_id(chat_and_edit_param.project_id)
        
        # Initialize the IssueContentGenerator with plan and tech spec
        content_generator = IssueContentGenerator(
            plan=plan.content if plan else "",
            tech_spec=tech_spec.content if tech_spec else "",
        )
        
        # Return a streaming response
        return StreamingResponse(
            process_stream(
                content_generator,
                chat_and_edit_param.message,
                history=chat_and_edit_param.history if chat_and_edit_param.history else [],
                issue_title=issue.title,
                issue_str=issue.description,
            ),
            media_type="application/x-ndjson",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving GitHub issue: {str(e)}"
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
