from fastapi import APIRouter, HTTPException, Depends, status
from typing import List

# from uuid import UUID # UUID を削除
from pydantic import BaseModel
from models.models import Project, Document
from repositories.projects import ProjectRepository
from repositories.documents import DocumentRepository
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
    repo: ProjectRepository = Depends(get_project_repository),
    plan_doc_repo: DocumentRepository = Depends(get_plan_document_repository),
    tech_spec_doc_repo: DocumentRepository = Depends(get_tech_spec_document_repository),
):
    """
    新しいプロジェクトを作成します。
    """
    try:
        # Project.create メソッドを使用
        new_project = Project.create(title=project_data.title)
        # save_or_update は string ID を返すようになった
        project_id_str = repo.save_or_update(new_project)

        plan_doc = Document(project_id=project_id_str, content="")
        plan_doc_repo.save_or_update(plan_doc)

        tech_spec_doc = Document(project_id=project_id_str, content="")
        tech_spec_doc_repo.save_or_update(tech_spec_doc)

        # get_by_id も string ID を受け付ける
        created_project = repo.get_by_id(project_id_str)
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
    project_id: str,  # UUID から str に変更
    repo: ProjectRepository = Depends(get_project_repository),
):
    """
    指定されたIDのプロジェクトを取得します。
    """
    try:
        project = repo.get_by_id(project_id)  # get_by_id は string ID を受け付ける
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
    repo: ProjectRepository = Depends(get_project_repository),
):
    """
    指定されたIDのプロジェクトを更新します。
    """
    try:
        existing_project = repo.get_by_id(
            project_id
        )  # get_by_id は string ID を受け付ける
        if existing_project is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project with ID '{project_id}' not found.",
            )

        # Project.update メソッドを使用
        existing_project.update(title=project_data.title)

        # save_or_update は string ID を返す
        updated_project_id_str = repo.save_or_update(existing_project)
        updated_project = repo.get_by_id(
            updated_project_id_str
        )  # get_by_id は string ID を受け付ける
        if updated_project is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve updated project.",
            )
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
    repo: ProjectRepository = Depends(get_project_repository),
):
    """
    指定されたIDのプロジェクトを削除します。
    """
    try:
        deleted = repo.delete_by_id(
            project_id
        )  # delete_by_id は string ID を受け付ける
        if not deleted:
            # delete_by_id が ValueError を raise するようになったので、
            # ここで 404 を返す必要はなくなったかもしれないが、念のため残す
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project with ID '{project_id}' not found or could not be deleted.",
            )
        return None  # 204 No Content を返す
    except ValueError as ve:  # リポジトリが ValueError を raise する場合
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(ve),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete project: {str(e)}",
        )
