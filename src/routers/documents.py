from fastapi import APIRouter, HTTPException, Depends, status
from models.document import Document
from repositories.documents import (
    DocumentRepository,
    PlanDocumentRepository,
    TechSpecDocumentRepository,
)
from routers.utils import (
    get_plan_document_repository,
    get_tech_spec_document_repository,
)

router = APIRouter()


def _save_or_update_document(
    document: Document,
    repo: DocumentRepository,
) -> dict:
    """Helper function to save or update a document."""
    try:
        doc_id = repo.save_or_update(document)
        return {"project_id": doc_id, "status": "success"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,  # statusコードを使用
            detail=f"Failed to save/update document: {str(e)}",
        )


def _get_document_by_id(
    project_id: str,
    repo: DocumentRepository,
) -> Document:
    """Helper function to get a document by ID."""
    try:
        document = repo.get_by_id(project_id)
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


@router.post("/plan")
def save_or_update_planning_document(
    document: Document,
    repo: PlanDocumentRepository = Depends(get_plan_document_repository),
):
    """
    Saves a new planning document or updates an existing one using the DocumentRepository.
    """
    return _save_or_update_document(document, repo)


@router.get("/plan/{project_id}", response_model=Document)
def get_planning_document(
    project_id: str,
    repo: PlanDocumentRepository = Depends(get_plan_document_repository),
):
    """
    Retrieves a planning document by its ID.
    """
    return _get_document_by_id(project_id, repo)


@router.post("/tech-spec")
def save_or_update_tech_spec_document(
    document: Document,
    repo: TechSpecDocumentRepository = Depends(get_tech_spec_document_repository),
):
    """
    Saves a new technical specification document or updates an existing one using the DocumentRepository.
    """
    return _save_or_update_document(document, repo)


@router.get("/tech-spec/{project_id}", response_model=Document)
def get_tech_spec_document(
    project_id: str,
    repo: TechSpecDocumentRepository = Depends(get_tech_spec_document_repository),
):
    """
    Retrieves a technical specification document by its ID.
    """
    return _get_document_by_id(project_id, repo)
