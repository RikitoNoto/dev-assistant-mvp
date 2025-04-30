from fastapi import APIRouter, HTTPException, Depends, status
from typing import List
from uuid import UUID
from pydantic import BaseModel  # BaseModelをインポート
from models import Project
from repositories.projects import ProjectRepository
from routers.utils import get_project_repository

# from datetime import datetime # datetimeはmodels.pyで使われるためここでは不要

router = APIRouter()


# Pydanticモデルをリクエスト/レスポンス用に定義 (関数の前に移動)
class ProjectCreate(BaseModel):
    title: str


class ProjectUpdate(BaseModel):
    title: str


@router.post("", response_model=Project, status_code=status.HTTP_201_CREATED)
def create_project(
    project_data: ProjectCreate,
    repo: ProjectRepository = Depends(get_project_repository),
):
    """
    新しいプロジェクトを作成します。
    """
    try:
        # Projectモデルインスタンスを作成（IDと日時は自動生成）
        new_project = Project(title=project_data.title)
        project_id = repo.save_or_update(new_project)
        # 保存されたプロジェクト情報を取得して返す（IDや日時が含まれる）
        created_project = repo.get_by_id(project_id)
        if created_project is None:
            # これは通常発生しないはずですが、念のため
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve created project.",
            )
        return created_project
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create project: {str(e)}",
        )


@router.get("", response_model=List[Project])
def get_all_projects(
    repo: ProjectRepository = Depends(get_project_repository),
):
    """
    すべてのプロジェクトを取得します。
    """
    try:
        projects = repo.get_all()
        return projects
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get projects: {str(e)}",
        )


@router.get("/{project_id}", response_model=Project)
def get_project_by_id(
    project_id: UUID,
    repo: ProjectRepository = Depends(get_project_repository),
):
    """
    指定されたIDのプロジェクトを取得します。
    """
    try:
        project = repo.get_by_id(project_id)
        if project is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project with ID '{project_id}' not found.",
            )
        return project
    except HTTPException as http_exc:
        raise http_exc  # 404エラーをそのまま返す
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get project: {str(e)}",
        )


@router.put("/{project_id}", response_model=Project)
def update_project(
    project_id: UUID,
    project_data: ProjectUpdate,
    repo: ProjectRepository = Depends(get_project_repository),
):
    """
    指定されたIDのプロジェクトを更新します。
    """
    try:
        existing_project = repo.get_by_id(project_id)
        if existing_project is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project with ID '{project_id}' not found.",
            )

        # 更新するフィールドを設定
        existing_project.title = project_data.title
        # updated_at は save_or_update 内で更新される

        updated_project_id = repo.save_or_update(existing_project)
        # 更新後のプロジェクト情報を取得して返す
        updated_project = repo.get_by_id(updated_project_id)
        if updated_project is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve updated project.",
            )
        return updated_project
    except HTTPException as http_exc:
        raise http_exc  # 404エラーをそのまま返す
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update project: {str(e)}",
        )


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: UUID,
    repo: ProjectRepository = Depends(get_project_repository),
):
    """
    指定されたIDのプロジェクトを削除します。
    """
    try:
        deleted = repo.delete_by_id(project_id)
        if not deleted:
            # delete_by_idがFalseを返すことはない想定だが、念のため
            # (存在しない場合はValueErrorが発生する)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,  # 実際にはValueErrorで捕捉されるはず
                detail=f"Project with ID '{project_id}' not found or could not be deleted.",
            )
        # 成功時はボディなしで204を返す
        return None
    except ValueError as ve:  # リポジトリで発生するValueErrorを捕捉
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(ve),  # エラーメッセージを詳細として返す
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete project: {str(e)}",
        )
