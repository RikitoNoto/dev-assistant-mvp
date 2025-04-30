from repositories.documents import (
    PlanDocumentRepository,
    TechSpecDocumentRepository,
    DynamoDbDocumentRepository as DynamoDbDocRepo,  # Alias to avoid name clash
)
from repositories.projects import (
    ProjectRepository,
    DynamoDbProjectRepository,
)

# Use a single instance for the repository to manage the table initialization correctly
# Note: In a real application, consider a more robust singleton pattern or dependency injection framework
_project_repository_instance = None


def get_project_repository() -> ProjectRepository:
    """Returns a singleton instance of the DynamoDbProjectRepository."""
    global _project_repository_instance
    if _project_repository_instance is None:
        _project_repository_instance = DynamoDbProjectRepository()
        # Initialize the table when the instance is first created
        _project_repository_instance.initialize("Projects")
    return _project_repository_instance


# Keep existing document repository functions, using the alias for DynamoDbDocumentRepository
def get_plan_document_repository() -> PlanDocumentRepository:
    # Consider initializing the table here as well if needed, or manage instances similarly
    repo = DynamoDbDocRepo("PlanningDocuments")
    # repo.initialize() # Uncomment if initialization is needed per instance/type
    return repo


def get_tech_spec_document_repository() -> TechSpecDocumentRepository:
    repo = DynamoDbDocRepo("TechSpecDocuments")
    # repo.initialize() # Uncomment if initialization is needed per instance/type
    return repo
