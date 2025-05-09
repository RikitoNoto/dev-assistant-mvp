from contextlib import asynccontextmanager
from fastapi import FastAPI
from routers import chat, documents, projects, issues
from routers.utils import (
    get_plan_document_repository,
    get_project_repository,
    get_tech_spec_document_repository,
    get_issue_repository,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load the ML model
    print("Initializing repositories...")
    # 各リポジトリのインスタンスを取得して初期化をトリガー
    plan_repo = get_plan_document_repository()
    if hasattr(plan_repo, "initialize"):  # DynamoDB実装の場合のみ初期化
        plan_repo.initialize("PlanningDocuments")

    tech_spec_repo = get_tech_spec_document_repository()
    if hasattr(tech_spec_repo, "initialize"):
        tech_spec_repo.initialize("TechSpecDocuments")

    get_project_repository()  # これでProjectテーブルも初期化される
    # initializeはget_project_repository内で呼ばれるためここでは不要

    issue_repo = get_issue_repository()
    if hasattr(issue_repo, "initialize"):
        issue_repo.initialize()

    print("Repositories initialized.")
    yield
    # Clean up the ML models and release the resources
    print("Cleaning up resources...")  # 必要であれば終了処理を追加


app = FastAPI(lifespan=lifespan)

# Include routers
app.include_router(chat.router, prefix="/chat", tags=["chat"])
app.include_router(documents.router, prefix="/documents", tags=["documents"])
app.include_router(projects.router, prefix="/projects", tags=["projects"])
app.include_router(issues.router, prefix="/issues", tags=["issues"])


if __name__ == "__main__":
    import uvicorn

    # uvicornの起動のみを行う
    uvicorn.run(app, host="0.0.0.0", port=8888)
