import os

from datetime import datetime
from fastapi import APIRouter, HTTPException, status
from models.document import PlanDocument, TechSpecDocument
from models.project import Project
from pydantic import BaseModel
from repositories.issues.github import GitHubIssuesRepository
from typing import List


router = APIRouter()


class ProjectCreate(BaseModel):
    title: str


class ProjectUpdate(BaseModel):
    title: str


class ProjectOpenUpdate(BaseModel):
    pass  # No fields needed, just updating last_opened_at


class GitHubProjectRegister(BaseModel):
    github_project_id: str


class GitHubProject(BaseModel):
    id: str
    name: str


@router.post("", response_model=Project, status_code=status.HTTP_201_CREATED)
def create_project(
    project_data: ProjectCreate,
):
    """
    新しいプロジェクトを作成します。
    """
    try:
        new_project = Project(title=project_data.title).create()

        plan_doc = PlanDocument(project_id=new_project.project_id, content="")
        plan_doc.create()
        

        tech_spec_doc = TechSpecDocument(project_id=new_project.project_id, content="")
        tech_spec_doc.create()

        # get_by_id も string ID を受け付ける
        created_project = Project.find_by_id(new_project.project_id)
        if created_project is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve created project.",
            )
        return created_project
    except Exception as e:
        print(f"Error creating project: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create project: {str(e)}",
        )


@router.get("", response_model=List[Project])
def get_all_projects():
    """
    すべてのプロジェクトを取得します。
    """
    try:
        projects = Project.find_all()
        return projects
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get projects: {str(e)}",
        )


@router.get("/{project_id}", response_model=Project)
def get_project_by_id(
    project_id: str,  # UUID から str に変更
):
    """
    指定されたIDのプロジェクトを取得します。
    """
    try:
        project = Project.find_by_id(project_id)
        if project is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project with ID '{project_id}' not found.",
            )
        return project
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get project: {str(e)}",
        )


@router.put("/{project_id}", response_model=Project)
def update_project(
    project_id: str,  # UUID から str に変更
    project_data: ProjectUpdate,
):
    """
    指定されたIDのプロジェクトを更新します。
    """
    try:
        existing_project = Project.find_by_id(
            project_id
        )
        if existing_project is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project with ID '{project_id}' not found.",
            )

        # Project.update メソッドを使用
        updated_project = existing_project.update(title=project_data.title)

        return updated_project
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update project: {str(e)}",
        )


@router.post("/{project_id}/open", response_model=Project)
def update_project_last_opened_at(
    project_id: str,
    _: ProjectOpenUpdate = ProjectOpenUpdate(),
):
    """
    プロジェクトを開いたときに last_opened_at を更新します。
    """
    try:
        existing_project = Project.find_by_id(project_id)
        if existing_project is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project with ID '{project_id}' not found.",
            )

        # last_opened_at を現在時刻に更新
        updated_project = existing_project.update(last_opened_at=datetime.now())

        return updated_project
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update project last_opened_at: {str(e)}",
        )


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: str,  # UUID から str に変更
):
    """
    指定されたIDのプロジェクトを削除します。
    """
    # プロジェクトの存在チェックをtry-exceptの外で行う
    project = Project.find_by_id(project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID '{project_id}' not found.",
        )
    
    try:
        deleted = project.delete()
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project with ID '{project_id}' not found or could not be deleted.",
            )
        return None  # 204 No Content を返す
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete project: {str(e)}",
        )


@router.post("/{project_id}/github", response_model=Project)
def register_github_project(
    project_id: str,
    github_project_data: GitHubProjectRegister,
):
    """
    プロジェクトにGitHubプロジェクトIDを登録します。
    
    Args:
        project_id: 登録対象のプロジェクトID
        github_project_data: GitHubプロジェクトIDを含むデータ
        
    Returns:
        Project: 更新されたプロジェクト
    """
    try:
        # プロジェクトの存在確認
        existing_project = Project.find_by_id(project_id)
        if existing_project is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project with ID '{project_id}' not found.",
            )
            
        # GitHubプロジェクトIDを登録
        updated_project = existing_project.update(github_project_id=github_project_data.github_project_id)
        
        return updated_project
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to register GitHub project: {str(e)}",
        )


def get_github_repository():
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


@router.get("/github/projects", response_model=List[GitHubProject])
def get_github_projects():
    """
    GitHubと連携しているプロジェクト一覧を取得します。
    
    Returns:
        List[GitHubProject]: GitHubプロジェクトのリスト
    """
    try:
        github_repo = get_github_repository()
        projects = github_repo.fetch_projects()
        return projects
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch GitHub projects: {str(e)}",
        )
        