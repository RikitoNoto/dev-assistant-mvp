from fastapi import APIRouter, HTTPException, Depends
from models import Document
from repositories import DocumentRepository
from routers.utils import get_document_repository

router = APIRouter()


async def _save_or_update_document(document: Document, repo: DocumentRepository):
    """Helper function to save or update a document."""
    try:
        doc_id = repo.save_or_update(document)
        return {"project_id": doc_id, "status": "success"}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to save/update document: {str(e)}"
        )


@router.post("/plan")
async def save_or_update_planning_document(
    document: Document, repo: DocumentRepository = Depends(get_document_repository)
):
    """
    Saves a new planning document or updates an existing one using the DocumentRepository.
    """
    return await _save_or_update_document(document, repo)


@router.post("/tech-spec")
async def save_or_update_tech_spec_document(
    document: Document, repo: DocumentRepository = Depends(get_document_repository)
):
    """
    Saves a new technical specification document or updates an existing one using the DocumentRepository.
    """
    return await _save_or_update_document(document, repo)
