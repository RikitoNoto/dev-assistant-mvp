import os
from repositories.data.documents import (
    PlanDocumentRepository,
    TechSpecDocumentRepository,
    DynamoDbDocumentRepository as DynamoDbDocRepo,
)
from repositories.data.projects import (
    ProjectRepository,
    DynamoDbProjectRepository,
)

from repositories.data.issues import IssueRepository, DynamoDbIssueRepository

_project_repository_instance = None


DEBUG = os.getenv("DEBUG", "False").lower() in ("true", "1", "t")

def get_project_repository() -> ProjectRepository:
    """Returns a singleton instance of the DynamoDbProjectRepository."""
    global _project_repository_instance
    if _project_repository_instance is None:
        _project_repository_instance = DynamoDbProjectRepository()
        _project_repository_instance.initialize("Projects")
    return _project_repository_instance


def get_plan_document_repository() -> PlanDocumentRepository:
    repo = DynamoDbDocRepo("PlanningDocuments")
    return repo


def get_tech_spec_document_repository() -> TechSpecDocumentRepository:
    repo = DynamoDbDocRepo("TechSpecDocuments")
    return repo


def get_issue_repository() -> IssueRepository:
    repo = DynamoDbIssueRepository("Issues")
    return repo
