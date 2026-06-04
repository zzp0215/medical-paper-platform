"""LLM 模块统一导出."""
from backend.llm.client import LLMClient
from backend.llm.exceptions import (
    LLMAuthError,
    LLMConnectionError,
    LLMContentFilterError,
    LLMContextLengthError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from backend.llm.models import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    EmbeddingData,
    EmbeddingRequest,
    EmbeddingResponse,
    TokenUsage,
    ToolDefinition,
)
from backend.llm.router import LLMRouter, resolve_model_chain

__all__ = [
    # 客户端
    "LLMClient",
    "LLMRouter",
    "resolve_model_chain",
    # 模型
    "ChatMessage",
    "ChatRequest",
    "ChatResponse",
    "EmbeddingData",
    "EmbeddingRequest",
    "EmbeddingResponse",
    "TokenUsage",
    "ToolDefinition",
    # 异常
    "LLMAuthError",
    "LLMConnectionError",
    "LLMContentFilterError",
    "LLMContextLengthError",
    "LLMRateLimitError",
    "LLMTimeoutError",
]
