"""LLM 模块专用异常."""
from __future__ import annotations

from backend.core import LLMError


class LLMConnectionError(LLMError):
    """连不上 LiteLLM Proxy."""

    code = "llm_connection_error"
    status_code = 503


class LLMRateLimitError(LLMError):
    """限流."""

    code = "llm_rate_limit"
    status_code = 429


class LLMAuthError(LLMError):
    """鉴权失败 (master key 错)."""

    code = "llm_auth_error"
    status_code = 401


class LLMTimeoutError(LLMError):
    """超时."""

    code = "llm_timeout"
    status_code = 504


class LLMContextLengthError(LLMError):
    """上下文超长."""

    code = "llm_context_length"
    status_code = 413


class LLMContentFilterError(LLMError):
    """内容被上游拒绝."""

    code = "llm_content_filter"
    status_code = 400
