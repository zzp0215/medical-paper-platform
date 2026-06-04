"""
LLM 客户端 (LiteLLM Proxy 适配).

设计
----
- 后端只用 OpenAI 兼容 SDK, 不直接连 DeepSeek/Anthropic/OpenAI
- 走 `http://litellm:4000` (容器内) 或 `http://localhost:4000` (本地开发)
- 异步优先 (OpenAI AsyncClient); 提供同步 fallback 给脚本/Celery 用
- 自动把 OpenAI SDK 抛的异常翻译为 LLMError 子类

使用
----
    from backend.llm.client import LLMClient

    async with LLMClient() as client:
        resp = await client.chat(
            ChatRequest(
                model="deepseek-chat",
                messages=[ChatMessage(role="user", content="hi")],
            )
        )
        print(resp.content)
"""
from __future__ import annotations

import asyncio
import os
import time
from collections.abc import AsyncIterator
from typing import Any

import httpx
from openai import (
    APIConnectionError,
    APITimeoutError,
    AsyncOpenAI,
    AuthenticationError,
    BadRequestError,
    NotFoundError,
    RateLimitError,
)

from backend.core import logger, settings
from backend.llm.exceptions import (
    LLMAuthError,
    LLMConnectionError,
    LLMContentFilterError,
    LLMContextLengthError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from backend.llm.models import (
    ChatRequest,
    ChatResponse,
    EmbeddingData,
    EmbeddingRequest,
    EmbeddingResponse,
    TokenUsage,
)

# LiteLLM 默认端口
DEFAULT_LITELLM_PORT = 4000


def _resolve_base_url() -> str:
    """根据环境推断 LiteLLM base URL.

    优先级: LITELLM_BASE_URL 环境变量 > settings 推导 > 默认
    """
    if url := os.getenv("LITELLM_BASE_URL"):
        return url.rstrip("/")
    # 容器内走服务名, 主机开发走 localhost
    if os.getenv("DOCKER_CONTAINER"):
        return f"http://litellm:{DEFAULT_LITELLM_PORT}/v1"
    return f"http://localhost:{DEFAULT_LITELLM_PORT}/v1"


def _resolve_api_key() -> str:
    if key := os.getenv("LITELLM_MASTER_KEY"):
        return key
    return settings.llm.deepseek_api_key  # fallback (不应该走到这)


class LLMClient:
    """LLM 异步客户端.

    用作 async context manager, 退出时关闭 HTTP 连接.
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float = 60.0,
        max_retries: int = 2,
    ) -> None:
        self.base_url = base_url or _resolve_base_url()
        self.api_key = api_key or _resolve_api_key()
        self.timeout = timeout
        self.max_retries = max_retries

        self._client: AsyncOpenAI | None = None
        self._http: httpx.AsyncClient | None = None

    # ============================================
    # 生命周期
    # ============================================
    async def __aenter__(self) -> "LLMClient":
        self._http = httpx.AsyncClient(timeout=self.timeout)
        self._client = AsyncOpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
            http_client=self._http,
            max_retries=0,  # 自己控制重试
            timeout=self.timeout,
        )
        logger.debug("LLMClient 初始化 | base={}", self.base_url)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._client:
            await self._client.close()
        if self._http:
            await self._http.aclose()
        logger.debug("LLMClient 关闭")

    # ============================================
    # Chat
    # ============================================
    async def chat(self, req: ChatRequest) -> ChatResponse:
        """单次 chat 调用 (含重试)."""
        if self._client is None:
            raise RuntimeError("LLMClient must be used as async context manager")

        payload = req.model_dump(exclude_none=True, exclude={"user_id", "trace_id"})
        # OpenAI SDK 的 messages 字段是 BaseModel, 需转 dict
        payload["messages"] = [m.model_dump(exclude_none=True) for m in req.messages]

        last_err: Exception | None = None
        for attempt in range(1, self.max_retries + 2):  # 1 + max_retries
            t0 = time.perf_counter()
            try:
                resp = await self._client.chat.completions.create(**payload)
                return self._parse_chat_response(req, resp, t0)
            except APIConnectionError as e:
                last_err = LLMConnectionError(f"连接 LiteLLM 失败: {e}")
            except APITimeoutError as e:
                last_err = LLMTimeoutError(f"LLM 调用超时: {e}")
            except RateLimitError as e:
                last_err = LLMRateLimitError(f"触发限流: {e}")
            except AuthenticationError as e:
                # 鉴权失败不重试
                raise LLMAuthError(f"鉴权失败 (检查 LITELLM_MASTER_KEY): {e}") from e
            except BadRequestError as e:
                msg = str(e)
                if "context_length_exceeded" in msg or "maximum context length" in msg:
                    raise LLMContextLengthError(f"上下文超长: {e}") from e
                if "content_filter" in msg or "content_policy" in msg:
                    raise LLMContentFilterError(f"内容被拒: {e}") from e
                raise  # 其它 4xx 不重试
            except NotFoundError as e:
                raise  # 模型不存在
            except Exception as e:
                last_err = e
                logger.warning("LLM 调用异常 (attempt {}/{}): {}", attempt, self.max_retries + 1, e)

            # 指数退避
            if attempt <= self.max_retries:
                await asyncio.sleep(0.5 * (2 ** (attempt - 1)))

        logger.error("LLM 调用重试耗尽 | model={} err={}", req.model, last_err)
        if last_err:
            raise last_err
        raise RuntimeError("LLM call failed without exception")

    async def stream_chat(self, req: ChatRequest) -> AsyncIterator[str]:
        """流式 chat (逐 token yield)."""
        if self._client is None:
            raise RuntimeError("LLMClient must be used as async context manager")

        req.stream = True
        payload = req.model_dump(exclude_none=True, exclude={"user_id", "trace_id"})
        payload["messages"] = [m.model_dump(exclude_none=True) for m in req.messages]
        payload["stream"] = True

        try:
            stream = await self._client.chat.completions.create(**payload)
            async for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta
        except APIConnectionError as e:
            raise LLMConnectionError(f"流式连接失败: {e}") from e

    # ============================================
    # Embedding
    # ============================================
    async def embed(self, req: EmbeddingRequest) -> EmbeddingResponse:
        if self._client is None:
            raise RuntimeError("LLMClient must be used as async context manager")

        try:
            resp = await self._client.embeddings.create(
                model=req.model,
                input=req.input,
                encoding_format=req.encoding_format,
            )
        except APIConnectionError as e:
            raise LLMConnectionError(f"Embedding 连接失败: {e}") from e
        except APITimeoutError as e:
            raise LLMTimeoutError(f"Embedding 超时: {e}") from e
        except AuthenticationError as e:
            raise LLMAuthError(f"Embedding 鉴权失败: {e}") from e

        return EmbeddingResponse(
            model=resp.model,
            data=[EmbeddingData(embedding=list(d.embedding), index=d.index) for d in resp.data],
            usage=TokenUsage(
                prompt_tokens=getattr(resp.usage, "prompt_tokens", 0),
                total_tokens=getattr(resp.usage, "total_tokens", 0),
                model=resp.model,
            ),
        )

    # ============================================
    # 内部
    # ============================================
    def _parse_chat_response(self, req: ChatRequest, resp: Any, t0: float) -> ChatResponse:
        """OpenAI ChatCompletion → 内部 ChatResponse."""
        choice = resp.choices[0]
        content = choice.message.content or ""
        usage = TokenUsage(
            prompt_tokens=getattr(resp.usage, "prompt_tokens", 0) if resp.usage else 0,
            completion_tokens=getattr(resp.usage, "completion_tokens", 0) if resp.usage else 0,
            total_tokens=getattr(resp.usage, "total_tokens", 0) if resp.usage else 0,
            model=resp.model,
        )
        return ChatResponse(
            id=resp.id,
            model=resp.model,
            content=content,
            finish_reason=choice.finish_reason,
            usage=usage,
            latency_ms=(time.perf_counter() - t0) * 1000,
        )
