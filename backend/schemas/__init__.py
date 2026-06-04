"""Schemas 统一导出."""
from backend.schemas.common import BaseSchema, ComponentHealth, ErrorResponse, HealthStatus, Ok, Page
from backend.schemas.document import (
    BatchUploadResponse,
    DocumentResponse,
    KnowledgeBaseCreate,
    KnowledgeBaseResponse,
    UploadResponse,
)
from backend.schemas.paper import (
    ChatRequest,
    ChatResponse,
    PaperCreateRequest,
    PaperListItem,
    PaperResponse,
    PaperUpdateRequest,
    SectionResponse,
)

__all__ = [
    "BaseSchema",
    "Ok",
    "ErrorResponse",
    "Page",
    "HealthStatus",
    "ComponentHealth",
    "UploadResponse",
    "BatchUploadResponse",
    "DocumentResponse",
    "KnowledgeBaseCreate",
    "KnowledgeBaseResponse",
    "PaperCreateRequest",
    "PaperUpdateRequest",
    "PaperResponse",
    "PaperListItem",
    "SectionResponse",
    "ChatRequest",
    "ChatResponse",
]
