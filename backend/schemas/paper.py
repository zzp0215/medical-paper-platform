"""论文相关 Schema."""
from __future__ import annotations

from datetime import datetime

from pydantic import Field

from backend.models.paper import PaperStatus, PaperType
from backend.schemas.common import BaseSchema


class PaperCreateRequest(BaseSchema):
    """创建论文请求."""

    title: str = Field(..., min_length=2, max_length=512, description="论文标题")
    paper_type: PaperType = Field(default=PaperType.REVIEW)
    target_language: str = Field(default="zh", pattern=r"^(zh|en)$")
    knowledge_base_ids: list[int] = Field(default_factory=list, description="关联知识库")
    outline: dict | None = Field(default=None, description="可选: 用户预定义大纲")


class PaperUpdateRequest(BaseSchema):
    title: str | None = Field(default=None, max_length=512)
    outline: dict | None = None
    status: PaperStatus | None = None
    metadata_json: dict | None = None


class PaperResponse(BaseSchema):
    id: int
    owner_id: int
    title: str
    paper_type: PaperType
    target_language: str
    status: PaperStatus
    progress: int
    outline: dict | None
    metadata_json: dict | None
    created_at: datetime
    updated_at: datetime


class PaperListItem(BaseSchema):
    """列表用 (裁剪字段, 减少 payload)."""

    id: int
    title: str
    paper_type: PaperType
    status: PaperStatus
    progress: int
    created_at: datetime
    updated_at: datetime


class SectionResponse(BaseSchema):
    id: int
    paper_id: int
    order_index: int
    heading: str
    section_type: str
    content_md: str | None
    word_count: int
    citations: list | None
    verification_report: dict | None


class ChatRequest(BaseSchema):
    """多轮对话修改请求."""

    paper_id: int
    message: str = Field(..., min_length=1, max_length=4000, description="用户指令")
    section_id: int | None = Field(default=None, description="限定修改某节; None=全文")


class ChatResponse(BaseSchema):
    paper_id: int
    reply: str
    diff: dict | None = Field(default=None, description="修改前后 diff (结构化)")
    sections_updated: list[int] = Field(default_factory=list)
