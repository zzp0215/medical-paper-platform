"""
LLM 调用数据模型.

设计
----
- 与 OpenAI Chat Completions API 对齐 (LiteLLM 代理后端时透传)
- ChatMessage 用 Pydantic 严格校验, 防止 Agent 之间传错结构
- 不在此处放业务字段 (temperature/max_tokens), 留到 ChatRequest
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Role = Literal["system", "user", "assistant", "tool", "function"]


class ChatMessage(BaseModel):
    """单条消息.

    字段对齐 OpenAI: role + content (+ 可选 name/tool_call_id).
    """

    role: Role
    content: str
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: list[dict] | None = None


class ToolDefinition(BaseModel):
    """工具定义 (用于 function calling)."""

    name: str
    description: str
    parameters: dict  # JSON Schema


class ChatRequest(BaseModel):
    """LLM 调用请求 (与 OpenAI Chat Completions 对齐子集)."""

    # 可选, 由 LLMRouter 注入 (或调用方手动指定)
    model: str = Field(default="", description="模型别名 (deepseek-chat / claude-sonnet / gpt-4o), LLMRouter 会自动注入")
    messages: list[ChatMessage]
    temperature: float = Field(default=0.3, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, ge=1, le=32000)
    top_p: float = Field(default=1.0, ge=0.0, le=1.0)
    tools: list[ToolDefinition] | None = None
    tool_choice: str | dict | None = None
    stream: bool = False
    # 业务标记
    user_id: int | None = Field(default=None, description="调用者用户 ID (审计用)")
    trace_id: str | None = Field(default=None, description="链路追踪 ID")


class TokenUsage(BaseModel):
    """Token 用量 + 费用."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    model: str = ""


class ChatResponse(BaseModel):
    """LLM 调用响应."""

    id: str
    model: str
    content: str
    finish_reason: str | None = None
    usage: TokenUsage
    latency_ms: float = 0.0
    raw: dict | None = Field(default=None, exclude=True, description="原始响应 (调试用)")


class EmbeddingRequest(BaseModel):
    """Embedding 请求."""

    model: str = Field(default="bge-m3", description="bge-m3 / text-embedding-3-small")
    input: list[str] | str
    encoding_format: Literal["float", "base64"] = "float"


class EmbeddingData(BaseModel):
    embedding: list[float]
    index: int = 0
    object: str = "embedding"


class EmbeddingResponse(BaseModel):
    model: str
    data: list[EmbeddingData]
    usage: TokenUsage
