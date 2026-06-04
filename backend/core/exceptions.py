"""
自定义异常体系.

设计
----
- 所有业务异常继承自 MedPaperError, 顶层捕获时统一处理
- 提供 `code` 字段给前端做 i18n 翻译, `message` 字段给用户展示
- HTTP 状态码由 exception_handler 决定, 业务层不感知
"""
from __future__ import annotations

from typing import Any


class MedPaperError(Exception):
    """平台基础异常."""

    code: str = "internal_error"
    status_code: int = 500

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


# ============================================
# 资源类
# ============================================
class NotFoundError(MedPaperError):
    code = "not_found"
    status_code = 404


class ConflictError(MedPaperError):
    code = "conflict"
    status_code = 409


class ForbiddenError(MedPaperError):
    code = "forbidden"
    status_code = 403


class UnauthorizedError(MedPaperError):
    code = "unauthorized"
    status_code = 401


# ============================================
# 业务类
# ============================================
class ParseError(MedPaperError):
    """PDF 解析失败."""

    code = "parse_error"
    status_code = 422


class RetrievalError(MedPaperError):
    """检索失败."""

    code = "retrieval_error"
    status_code = 502


class LLMError(MedPaperError):
    """LLM 调用失败."""

    code = "llm_error"
    status_code = 502


class StorageError(MedPaperError):
    """对象存储失败."""

    code = "storage_error"
    status_code = 502


# ============================================
# 验证类
# ============================================
class ValidationError(MedPaperError):
    """业务校验失败 (区别于 Pydantic 校验)."""

    code = "validation_error"
    status_code = 422


class RateLimitError(MedPaperError):
    code = "rate_limit"
    status_code = 429
