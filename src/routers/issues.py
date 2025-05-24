from fastapi import APIRouter, HTTPException, status, Path, Query, Depends
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from models.issue import Issue
import os
from datetime import datetime
from repositories.issues.github import GitHubIssuesRepository
from repositories.issues.issues_repository import IssueData

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


def get_github_repository() -> GitHubIssuesRepository:
    """
    GitHub APIを使用するためのリポジトリインスタンスを取得します。
    
    Returns:
        GitHubIssuesRepository: GitHub APIリポジトリのインスタンス
    """
    github_token = os.getenv("GITHUB_TOKEN")
    if not github_token:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GitHub token is not configured. Please set the GITHUB_TOKEN environment variable.",
        )
    return GitHubIssuesRepository(token=github_token)


class GitHubIssueFilter(BaseModel):
    state: Optional[str] = None
    labels: Optional[List[str]] = None
    limit_per_repo: Optional[int] = 100


class GitHubIssueResponse(BaseModel):
    id: str
    title: str
    description: str
    url: str
    status: str
    created_at: datetime
    updated_at: datetime
    labels: List[str] = []
    project_status: Optional[str] = None


@router.get("/{project_id}/github", response_model=List[GitHubIssueResponse])
def get_github_issues(
    project_id: str = Path(..., description="The ID of the local project"),
    state: Optional[str] = Query(None, description="Filter issues by state (OPEN, CLOSED)"),
    labels: Optional[str] = Query(None, description="Filter issues by labels (comma-separated)"),
    limit_per_repo: int = Query(100, description="Maximum number of issues to fetch per repository")
):
    """
    プロジェクトに紐づけられたGitHubプロジェクトからIssueを取得します。
    
    Args:
        project_id: ローカルプロジェクトID
        state: Issueの状態でフィルタリング（OPEN、CLOSED）
        labels: Issueのラベルでフィルタリング（カンマ区切り）
        limit_per_repo: リポジトリごとに取得するIssueの最大数
        
    Returns:
        List[GitHubIssueResponse]: GitHubのIssueリスト
    """
    try:
        # プロジェクトモデルをインポート
        from models.project import Project
        
        # プロジェクトを取得
        project = Project.find_by_id(project_id)
        if project is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project with ID '{project_id}' not found."
            )
        
        # GitHubプロジェクトIDが設定されているか確認
        if not project.github_project_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Project with ID '{project_id}' is not linked to a GitHub project."
            )
        
        # GitHubリポジトリインスタンスを取得
        github_repo = get_github_repository()
        
        # ラベルの処理（カンマ区切りの文字列をリストに変換）
        label_list = None
        if labels:
            label_list = [label.strip() for label in labels.split(',')]
        
        # GitHubからIssueを取得（プロジェクトのGitHubプロジェクトIDを使用）
        issues = github_repo.fetch_issues(
            project_id=project.github_project_id,
            state=state,
            labels=label_list,
            limit_per_repo=limit_per_repo
        )
        
        # IssueDataオブジェクトをレスポンスモデルに変換
        response_issues = []
        for issue in issues:
            response_issues.append(GitHubIssueResponse(
                id=issue.id,
                title=issue.title,
                description=issue.description,
                url=issue.url,
                status=issue.status,
                created_at=issue.created_at,
                updated_at=issue.updated_at,
                labels=issue.labels,
                project_status=issue.project_status
            ))
        
        return response_issues
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch GitHub issues: {str(e)}",
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


class GitHubIssueCreate(BaseModel):
    title: str
    description: str
    labels: Optional[List[str]] = None


class GitHubIssueUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    project_status: Optional[str] = None


@router.post("/{project_id}/github", response_model=GitHubIssueResponse, status_code=status.HTTP_201_CREATED)
def create_github_issue(
    issue_data: GitHubIssueCreate,
    project_id: str = Path(..., description="The ID of the local project")
):
    """
    GitHubに新しいIssueを作成します。
    
    Args:
        project_id: ローカルプロジェクトID
        issue_data: 作成するIssueのデータ（リポジトリ情報、タイトル、説明、ラベル）
        
    Returns:
        GitHubIssueResponse: 作成されたGitHub Issueの情報
    """
    try:
        # プロジェクトモデルをインポート
        from models.project import Project
        
        # プロジェクトを取得
        project = Project.find_by_id(project_id)
        if project is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project with ID '{project_id}' not found."
            )
        
        # GitHubプロジェクトIDが設定されているか確認
        if not project.github_project_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Project with ID '{project_id}' is not linked to a GitHub project."
            )
        
        # GitHubリポジトリインスタンスを取得
        github_repo = get_github_repository()
        
        # プロジェクトに紐づくリポジトリを取得
        repositories = github_repo.get_project_repositories(project.github_project_id)
        
        if not repositories:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No repositories found for project with ID '{project_id}'."
            )
        
        # 最初のリポジトリを使用してIssueを作成
        #TODO: 複数のリポジトリに対応する
        repository = repositories[0]
        
        # GitHub Issueを作成
        created_issue = github_repo.create_issue(
            repository_owner=repository["owner"],
            repository_name=repository["name"],
            title=issue_data.title,
            description=issue_data.description,
            labels=issue_data.labels
        )
        
        if not created_issue:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create GitHub issue."
            )
            
        # 作成したIssueをGitHub Projectsに追加
        added_to_project = github_repo.add_issue_to_project(
            project_id=project.github_project_id,
            issue_id=created_issue.id
        )
        
        if not added_to_project:
            # プロジェクトへの追加に失敗しても、Issue自体は作成されているので警告ログを出力
            print(f"Warning: Issue created but failed to add to project {project.github_project_id}")
        
        # レスポンスモデルに変換して返す
        return GitHubIssueResponse(
            id=created_issue.id,
            title=created_issue.title,
            description=created_issue.description,
            url=created_issue.url,
            status=created_issue.status,
            created_at=created_issue.created_at,
            updated_at=created_issue.updated_at,
            labels=created_issue.labels,
            project_status=created_issue.project_status
        )
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve)
        )
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create GitHub issue: {str(e)}",
        )


@router.put("/{project_id}/github/{issue_id}", response_model=GitHubIssueResponse)
def update_github_issue(
    issue_data: GitHubIssueUpdate,
    project_id: str = Path(..., description="The ID of the local project"),
    issue_id: str = Path(..., description="The ID of the GitHub issue"),
):
    """
    GitHubのIssueを編集します。
    
    Args:
        project_id: ローカルプロジェクトID
        issue_id: 編集するGitHub IssueのID
        issue_data: 更新するデータ（タイトル、説明、ステータス）
        
    Returns:
        GitHubIssueResponse: 更新されたGitHub Issueの情報
    """
    try:
        # プロジェクトモデルをインポート
        from models.project import Project
        
        # プロジェクトを取得
        project = Project.find_by_id(project_id)
        if project is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project with ID '{project_id}' not found."
            )
        
        # GitHubプロジェクトIDが設定されているか確認
        if not project.github_project_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Project with ID '{project_id}' is not linked to a GitHub project."
            )
        
        # GitHubリポジトリインスタンスを取得
        github_repo = get_github_repository()
        
        # GitHub Issueを更新
        updated_issue = github_repo.update_issue(
            issue_id=issue_id,
            title=issue_data.title,
            description=issue_data.description,
            status=issue_data.status,
            project_status=issue_data.project_status
        )
        
        if not updated_issue:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"GitHub Issue with ID '{issue_id}' not found or could not be updated."
            )
        
        # レスポンスモデルに変換して返す
        return GitHubIssueResponse(
            id=updated_issue.id,
            title=updated_issue.title,
            description=updated_issue.description,
            url=updated_issue.url,
            status=updated_issue.status,
            created_at=updated_issue.created_at,
            updated_at=updated_issue.updated_at,
            labels=updated_issue.labels,
            project_status=updated_issue.project_status
        )
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve)
        )
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update GitHub issue: {str(e)}",
        )


@router.delete("/{project_id}/github/{issue_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_github_issue(
    project_id: str = Path(..., description="The ID of the local project"),
    issue_id: str = Path(..., description="The ID of the GitHub issue"),
):
    """
    GitHubのIssueを削除します。
    
    Args:
        project_id: ローカルプロジェクトID
        issue_id: 削除するGitHub IssueのID
        
    Returns:
        None: 削除が成功した場合は204 No Contentを返します
    """
    try:
        # プロジェクトモデルをインポート
        from models.project import Project
        
        # プロジェクトを取得
        project = Project.find_by_id(project_id)
        if project is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project with ID '{project_id}' not found."
            )
        
        # GitHubプロジェクトIDが設定されているか確認
        if not project.github_project_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Project with ID '{project_id}' is not linked to a GitHub project."
            )
        
        # GitHubリポジトリインスタンスを取得
        github_repo = get_github_repository()
        
        # GitHub Issueを削除
        success = github_repo.delete_issue(issue_id=issue_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"GitHub Issue with ID '{issue_id}' not found or could not be deleted."
            )
        
        # 削除成功の場合は204 No Contentを返す
        return None
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete GitHub issue: {str(e)}",
        )
