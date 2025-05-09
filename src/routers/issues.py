from fastapi import APIRouter, HTTPException, Depends, status as http_status, Path, Query
from typing import List, Optional
from models import Issue
from repositories.issues import IssueRepository
from routers.utils import get_issue_repository

router = APIRouter()


def _save_or_update_issue(
    issue: Issue,
    repo: IssueRepository,
) -> dict:
    """Helper function to save or update an issue."""
    try:
        issue_id = repo.save_or_update(issue)
        return {"issue_id": issue_id, "project_id": issue.project_id, "status": "success"}
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save/update issue: {str(e)}",
        )


def _get_issue_by_id(
    project_id: str,
    issue_id: str,
    repo: IssueRepository,
) -> Issue:
    """Helper function to get an issue by ID."""
    try:
        issue = repo.get_by_id(project_id, issue_id)
        if issue is None:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Issue with ID '{issue_id}' not found in project '{project_id}'.",
            )
        return issue
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get issue: {str(e)}",
        )


@router.post("/")
def save_or_update_issue(
    issue: Issue,
    repo: IssueRepository = Depends(get_issue_repository),
):
    """
    Saves a new issue or updates an existing one using the IssueRepository.
    """
    return _save_or_update_issue(issue, repo)


@router.get("/{project_id}/{issue_id}", response_model=Issue)
def get_issue(
    project_id: str = Path(..., description="The ID of the project"),
    issue_id: str = Path(..., description="The ID of the issue"),
    repo: IssueRepository = Depends(get_issue_repository),
):
    """
    Retrieves an issue by its project ID and issue ID.
    """
    return _get_issue_by_id(project_id, issue_id, repo)


@router.get("/{project_id}", response_model=List[Issue])
def get_issues_by_project(
    project_id: str = Path(..., description="The ID of the project"),
    status: Optional[str] = Query(None, description="Filter issues by status"),
    repo: IssueRepository = Depends(get_issue_repository),
):
    """
    Retrieves all issues for a specific project.
    Optionally filter by status if provided.
    """
    try:
        issues = repo.get_by_project_id(project_id)
        
        # Filter by status if provided
        if status:
            issues = [issue for issue in issues if issue.status == status]
            
        return issues
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get issues for project: {str(e)}",
        )


@router.delete("/{project_id}/{issue_id}")
def delete_issue(
    project_id: str = Path(..., description="The ID of the project"),
    issue_id: str = Path(..., description="The ID of the issue"),
    repo: IssueRepository = Depends(get_issue_repository),
):
    """
    Deletes an issue by its project ID and issue ID.
    """
    try:
        # First check if the issue exists
        _get_issue_by_id(project_id, issue_id, repo)
        
        # If no exception was raised, proceed with deletion
        repo.delete(project_id, issue_id)
        return {"status": "success", "message": f"Issue {issue_id} deleted successfully"}
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete issue: {str(e)}",
        )
