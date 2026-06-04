"""通用响应/分页/错误模型."""
from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class BaseSchema(BaseModel):
    """所有 Schema 基类."""

    model_config = ConfigDict(
        from_attributes=True,  # 支持 ORM 对象直接转 schema
        populate_by_name=True,
        use_enum_values=True,
        str_strip_whitespace=True,
    )


# ============================================
# 响应包装
# ============================================
class Ok(BaseSchema, Generic[T]):
    """统一成功响应: {\"code\": 0, \"data\": ...}."""

    code: int = Field(default=0, description="0 表示成功, 非 0 见 error_codes.md")
    data: T | None = None
    message: str = "ok"


class ErrorResponse(BaseSchema):
    """统一错误响应."""

    code: str
    message: str
    details: dict[str, Any] | None = None
    request_id: str | None = None


# ============================================
# 分页
# ============================================
class Page(BaseSchema, Generic[T]):
    """分页结果."""

    items: list[T]
    total: int
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    has_next: bool = False

    @classmethod
    def of(cls, items: list[T], total: int, page: int = 1, page_size: int = 20) -> "Page[T]":
        return cls(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            has_next=(page * page_size) < total,
        )


# ============================================
# 健康检查
# ============================================
class HealthStatus(BaseSchema):
    status: str = "ok"
    version: str
    env: str
    components: dict[str, "ComponentHealth"]


class ComponentHealth(BaseSchema):
    status: str  # "up" | "down" | "degraded"
    latency_ms: float | None = None
    detail: str | None = None
