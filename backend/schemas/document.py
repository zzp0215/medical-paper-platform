"""上传 / 文献相关 Schema."""
from __future__ import annotations

from datetime import datetime

from pydantic import Field

from backend.models.knowledge_base import DocumentStatus
from backend.schemas.common import BaseSchema


class KnowledgeBaseCreate(BaseSchema):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    specialty: str | None = Field(default=None, max_length=64)


class KnowledgeBaseResponse(BaseSchema):
    id: int
    name: str
    description: str | None
    specialty: str | None
    ragflow_dataset_id: str | None
    doc_count: int
    chunk_count: int
    created_at: datetime


class UploadResponse(BaseSchema):
    """单文件上传结果."""

    document_id: int
    filename: str
    size: int
    sha256: str
    status: DocumentStatus
    is_duplicate: bool = Field(default=False, description="文件哈希已存在时标记")
    task_id: int | None = Field(default=None, description="Celery 任务 ID, 供进度查询")


class BatchUploadResponse(BaseSchema):
    total: int
    accepted: int
    duplicates: int
    rejected: int
    items: list[UploadResponse]


class DocumentResponse(BaseSchema):
    id: int
    kb_id: int
    title: str
    authors: list | None
    journal: str | None
    year: int | None
    doi: str | None
    status: DocumentStatus
    file_size: int
    created_at: datetime
