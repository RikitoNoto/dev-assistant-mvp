from fastapi import APIRouter, HTTPException, Depends
from models import Document
from repositories import (
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
            status_code=500, detail=f"Failed to save/update document: {str(e)}"
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


@router.post("/tech-spec")
def save_or_update_tech_spec_document(
    document: Document,
    repo: TechSpecDocumentRepository = Depends(get_tech_spec_document_repository),
):
    """
    Saves a new technical specification document or updates an existing one using the DocumentRepository.
    """
    return _save_or_update_document(document, repo)
