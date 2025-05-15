from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, status
from typing import Annotated, List

from pydantic import BaseModel
from models.document import Document
from models.project import Project
from repositories.documents import DocumentRepository
from repositories.projects import ProjectRepository
from routers.utils import (
    get_project_repository,
    get_plan_document_repository,
    get_tech_spec_document_repository,
)


router = APIRouter()


class ProjectCreate(BaseModel):
    title: str


class ProjectUpdate(BaseModel):
    title: str


@router.post("", response_model=Project, status_code=status.HTTP_201_CREATED)
def create_project(
    project_data: ProjectCreate,
    plan_doc_repo:DocumentRepository= Depends(get_plan_document_repository),
    tech_spec_doc_repo:DocumentRepository= Depends(get_tech_spec_document_repository),
):
    """
    新しいプロジェクトを作成します。
    """
    try:
        new_project = Project(title=project_data.title).create()

        plan_doc = Document(project_id=new_project.project_id, content="")
        plan_doc_repo.save_or_update(plan_doc)

        tech_spec_doc = Document(project_id=new_project.project_id, content="")
        tech_spec_doc_repo.save_or_update(tech_spec_doc)

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
        