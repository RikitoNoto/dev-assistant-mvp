from fastapi import FastAPI
from routers import chat, documents
from routers.utils import get_plan_document_repository

app = FastAPI()

# Include routers
app.include_router(chat.router, prefix="/chat", tags=["chat"])
app.include_router(documents.router, prefix="/documents", tags=["documents"])


if __name__ == "__main__":
    import uvicorn

    # Initialize repository (consider moving this to startup event if needed)
    repo = get_plan_document_repository()
    repo.initialize_table()

    uvicorn.run(app, host="0.0.0.0", port=8888)
