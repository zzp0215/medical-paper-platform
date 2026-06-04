"""
LLM 路由策略 (按场景选模型 + 降级链).

策略
----
- cost_first (默认): DeepSeek 优先, 失败降级到 Claude
- quality_first:    Claude 优先, 失败降级到 DeepSeek
- manual:           调用方显式指定 model, 不做自动路由

降级链
------
1. 主模型失败 → 备用模型
2. 备用失败 → 抛 LLMError (给上层处理)
"""
from __future__ import annotations

from typing import Literal

from backend.core import logger, settings
from backend.llm.client import LLMClient
from backend.llm.models import ChatRequest, ChatResponse

Strategy = Literal["cost_first", "quality_first", "manual"]


# ============================================
# 模型路由表
# ============================================
# 命名约定: 业务层用 logical_name, 实际 LiteLLM 别名
ROUTING_TABLE: dict[str, dict[str, list[str]]] = {
    "cost_first": {
        # 业务场景 → [主, 备]
        "default": ["deepseek-chat", "claude-sonnet"],
        "writing": ["deepseek-chat", "claude-sonnet"],
        "planning": ["deepseek-chat", "claude-sonnet"],
        "verification": ["deepseek-chat", "claude-sonnet"],
        "translation": ["deepseek-chat", "claude-sonnet"],
        "polish": ["claude-sonnet", "deepseek-chat"],
        "embedding": ["text-embedding-3-small"],
    },
    "quality_first": {
        "default": ["claude-sonnet", "deepseek-chat"],
        "writing": ["claude-sonnet", "deepseek-chat"],
        "planning": ["claude-sonnet", "deepseek-chat"],
        "verification": ["claude-sonnet", "deepseek-chat"],
        "translation": ["claude-sonnet", "deepseek-chat"],
        "polish": ["claude-sonnet", "deepseek-chat"],
        "embedding": ["text-embedding-3-small"],
    },
}


def resolve_model_chain(
    scenario: str = "default",
    strategy: Strategy | None = None,
    explicit_model: str | None = None,
) -> list[str]:
    """解析模型降级链.

    Args:
        scenario: 业务场景 (writing / planning / verification / ...)
        strategy: 路由策略 (None = 读 settings.llm.router_strategy)
        explicit_model: 调用方显式指定 (manual 模式)

    Returns:
        模型别名列表, 顺序 = 尝试顺序
    """
    if explicit_model:
        return [explicit_model]

    strategy = strategy or settings.llm.router_strategy
    table = ROUTING_TABLE.get(strategy, ROUTING_TABLE["cost_first"])
    return table.get(scenario, table["default"])


# ============================================
# 高层调用入口
# ============================================
class LLMRouter:
    """带降级链的 LLM 调用.

    用法:
        async with LLMRouter() as router:
            resp = await router.chat(
                scenario="writing",
                request=ChatRequest(messages=[...]),
            )
    """

    def __init__(
        self,
        strategy: Strategy | None = None,
        client: LLMClient | None = None,
    ) -> None:
        self.strategy = strategy or settings.llm.router_strategy
        self._client = client
        self._owned_client = client is None

    async def __aenter__(self) -> "LLMRouter":
        if self._client is None:
            self._client = LLMClient()
            await self._client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._owned_client and self._client:
            await self._client.__aexit__(exc_type, exc, tb)
            self._client = None

    async def chat(
        self,
        request: ChatRequest,
        scenario: str = "default",
    ) -> ChatResponse:
        """执行 chat 调用, 自动按降级链重试."""
        assert self._client is not None, "Use as async context manager"

        chain = resolve_model_chain(
            scenario=scenario,
            strategy=self.strategy,
            explicit_model=request.model if self.strategy == "manual" else None,
        )

        last_err: Exception | None = None
        for model_name in chain:
            try:
                request.model = model_name
                logger.info(
                    "LLM 调用 | scenario={} model={} strategy={} msgs={}",
                    scenario, model_name, self.strategy, len(request.messages),
                )
                resp = await self._client.chat(request)
                logger.info(
                    "LLM 成功 | model={} latency={:.0f}ms tokens={}",
                    resp.model, resp.latency_ms, resp.usage.total_tokens,
                )
                return resp
            except Exception as e:
                last_err = e
                logger.warning(
                    "LLM 降级 | scenario={} model={} 失败: {} | 尝试下一档",
                    scenario, model_name, type(e).__name__,
                )
                continue

        # 全部失败
        logger.error("LLM 降级链全部失败 | scenario={} chain={}", scenario, chain)
        if last_err:
            raise last_err
        raise RuntimeError("LLM call failed without exception")
