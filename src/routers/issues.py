from fastapi import APIRouter, HTTPException, status, Path, Query
from typing import List, Optional
from pydantic import BaseModel
from models.issue import Issue

router = APIRouter()


class IssueCreate(BaseModel):
    project_id: str
    title: str
    description: Optional[str] = ""
    status: Optional[str] = "todo"


class IssueUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_issue(issue_data: IssueCreate):
    """
    新しいIssueを作成します。
    """
    try:
        new_issue = Issue(
            project_id=issue_data.project_id,
            title=issue_data.title,
            description=issue_data.description,
            status=issue_data.status
        ).create()
        
        return new_issue
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create issue: {str(e)}",
        )


@router.get("/{project_id}/{issue_id}", response_model=Issue)
def get_issue(
    project_id: str = Path(..., description="The ID of the project"),
    issue_id: str = Path(..., description="The ID of the issue"),
):
    """
    プロジェクトIDとIssue IDによってIssueを取得します。
    """
    try:
        issue = Issue.find_by_id(project_id, issue_id)
        if issue is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Issue with ID '{issue_id}' not found in project '{project_id}'.",
            )
        return issue
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get issue: {str(e)}",
        )


@router.get("/{project_id}", response_model=List[Issue])
def get_issues_by_project(
    project_id: str = Path(..., description="The ID of the project"),
    status_filter: Optional[str] = Query(None, description="Filter issues by status", alias="status"),
):
    """
    プロジェクトに関連する全てのIssueを取得します。
    オプションでステータスによるフィルタリングが可能です。
    """
    try:
        issues = Issue.find_by_project_id(project_id)
        
        # Filter by status if provided
        if status_filter:
            issues = [issue for issue in issues if issue.status == status_filter]
            
        return issues
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get issues for project: {str(e)}",
        )


@router.put("/{project_id}/{issue_id}", response_model=Issue)
def update_issue(
    issue_data: IssueUpdate,
    project_id: str = Path(..., description="The ID of the project"),
    issue_id: str = Path(..., description="The ID of the issue"),
):
    """
    指定されたIssueを更新します。
    """
    try:
        existing_issue = Issue.find_by_id(project_id, issue_id)
        if existing_issue is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Issue with ID '{issue_id}' not found in project '{project_id}'.",
            )
        
        # 更新するフィールドを準備
        update_data = {}
        if issue_data.title is not None:
            update_data["title"] = issue_data.title
        if issue_data.description is not None:
            update_data["description"] = issue_data.description
        if issue_data.status is not None:
            update_data["status"] = issue_data.status
        
        # Issue.update メソッドを使用して更新
        updated_issue = existing_issue.update(**update_data)
        
        return updated_issue
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update issue: {str(e)}",
        )


@router.delete("/{project_id}/{issue_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_issue(
    project_id: str = Path(..., description="The ID of the project"),
    issue_id: str = Path(..., description="The ID of the issue"),
):
    """
    指定されたIssueを削除します。
    """
    # Issueの存在チェック
    issue = Issue.find_by_id(project_id, issue_id)
    if issue is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Issue with ID '{issue_id}' not found in project '{project_id}'.",
        )
    
    try:
        issue.delete()
        return None  # 204 No Content を返す
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete issue: {str(e)}",
        )
