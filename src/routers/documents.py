from fastapi import APIRouter, HTTPException, status
from models.document import Document
from repositories.documents import (
    PlanDocumentRepository,
    TechSpecDocumentRepository,
)
from routers.utils import (
    get_plan_document_repository,
    get_tech_spec_document_repository,
)

router = APIRouter()


@router.post("/plan")
def save_or_update_planning_document(document: Document):
    """
    Saves a new planning document or updates an existing one.
    """
    try:
        # ドキュメントを保存
        saved_document = document.save()
        return {"project_id": saved_document.document_id, "status": "success"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save/update document: {str(e)}",
        )


@router.get("/plan/{project_id}", response_model=Document)
def get_planning_document(project_id: str):
    """
    Retrieves a planning document by its ID.
    """
    try:
        # ドキュメントを検索
        document = Document.find_by_id(project_id)
        if document is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document with ID '{project_id}' not found.",
            )
        return document
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get document: {str(e)}",
        )


@router.post("/tech-spec")
def save_or_update_tech_spec_document(document: Document):
    """
    Saves a new technical specification document or updates an existing one.
    """
    try:
        # ドキュメントを保存
        saved_document = document.save()
        return {"project_id": saved_document.document_id, "status": "success"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save/update document: {str(e)}",
        )


@router.get("/tech-spec/{project_id}", response_model=Document)
def get_tech_spec_document(project_id: str):
    """
    Retrieves a technical specification document by its ID.
    """
    try:
        # ドキュメントを検索
        document = Document.find_by_id(project_id)
        if document is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document with ID '{project_id}' not found.",
            )
        return document
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get document: {str(e)}",
        )
