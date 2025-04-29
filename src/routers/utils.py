from repositories import DocumentRepository, DynamoDbDocumentRepository


def get_plan_document_repository() -> DocumentRepository:
    return DynamoDbDocumentRepository("PlanningDocuments")


def get_tech_spec_document_repository() -> DocumentRepository:
    return DynamoDbDocumentRepository("TechSpecDocuments")
