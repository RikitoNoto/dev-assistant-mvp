from repositories import (
    PlanDocumentRepository,
    TechSpecDocumentRepository,
    DynamoDbDocumentRepository,
)


def get_plan_document_repository() -> PlanDocumentRepository:
    return DynamoDbDocumentRepository("PlanningDocuments")


def get_tech_spec_document_repository() -> TechSpecDocumentRepository:
    return DynamoDbDocumentRepository("TechSpecDocuments")
