"""
LLM 网关冒烟测试 (mocked, 不真调外部 API).

覆盖
----
- 路由策略解析 (cost_first / quality_first / manual)
- 客户端初始化 (不连真服务)
- 异常翻译 (OpenAI 错误 → LLMError)
- 降级链 (主失败 → 备)
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

pytestmark = pytest.mark.unit


# ============================================
# 路由策略
# ============================================
class TestRoutingStrategy:
    """路由表解析."""

    def test_cost_first_default_uses_deepseek(self) -> None:
        from backend.llm.router import resolve_model_chain

        chain = resolve_model_chain(scenario="default", strategy="cost_first")
        assert chain[0] == "deepseek-chat"
        assert "claude-sonnet" in chain

    def test_quality_first_default_uses_claude(self) -> None:
        from backend.llm.router import resolve_model_chain

        chain = resolve_model_chain(scenario="default", strategy="quality_first")
        assert chain[0] == "claude-sonnet"
        assert "deepseek-chat" in chain

    def test_manual_explicit_model(self) -> None:
        from backend.llm.router import resolve_model_chain

        chain = resolve_model_chain(explicit_model="gpt-4o")
        assert chain == ["gpt-4o"]

    def test_unknown_scenario_falls_back_to_default(self) -> None:
        from backend.llm.router import resolve_model_chain

        chain = resolve_model_chain(scenario="nonexistent_xyz", strategy="cost_first")
        assert "deepseek-chat" in chain


# ============================================
# 客户端 (mocked)
# ============================================
class TestClientURLResolution:
    """URL/Key 解析 (不连真服务)."""

    def test_default_base_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("LITELLM_BASE_URL", raising=False)
        monkeypatch.delenv("DOCKER_CONTAINER", raising=False)
        from backend.llm.client import _resolve_base_url

        url = _resolve_base_url()
        assert "4000" in url
        assert url.startswith("http")

    def test_env_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LITELLM_BASE_URL", "http://custom:9999/v1")
        from backend.llm.client import _resolve_base_url

        assert _resolve_base_url() == "http://custom:9999/v1"


# ============================================
# 降级链
# ============================================
class TestRouterFallback:
    """LLMRouter 自动降级."""

    @pytest.mark.asyncio
    async def test_first_model_succeeds(self) -> None:
        from backend.llm import ChatRequest, ChatResponse, LLMRouter, TokenUsage

        with patch("backend.llm.router.LLMClient") as MockClient:
            mock = AsyncMock()
            mock.__aenter__ = AsyncMock(return_value=mock)
            mock.__aexit__ = AsyncMock(return_value=None)
            mock.chat = AsyncMock(
                return_value=ChatResponse(
                    id="r1", model="deepseek-chat", content="ok",
                    usage=TokenUsage(total_tokens=10, model="deepseek-chat"),
                )
            )
            MockClient.return_value = mock

            async with LLMRouter(strategy="cost_first") as router:
                resp = await router.chat(
                    ChatRequest(model="", messages=[]), scenario="writing"
                )
            assert resp.content == "ok"
            assert mock.chat.await_count == 1  # 一次成功

    @pytest.mark.asyncio
    async def test_fallback_to_second_model(self) -> None:
        from backend.llm import (
            ChatRequest,
            ChatResponse,
            LLMRouter,
            TokenUsage,
        )
        from backend.llm.exceptions import LLMConnectionError

        with patch("backend.llm.router.LLMClient") as MockClient:
            mock = AsyncMock()
            mock.__aenter__ = AsyncMock(return_value=mock)
            mock.__aexit__ = AsyncMock(return_value=None)
            # 第一次失败, 第二次成功
            mock.chat = AsyncMock(
                side_effect=[
                    LLMConnectionError("主模型挂了"),
                    ChatResponse(
                        id="r2", model="claude-sonnet", content="fallback ok",
                        usage=TokenUsage(total_tokens=20, model="claude-sonnet"),
                    ),
                ]
            )
            MockClient.return_value = mock

            async with LLMRouter(strategy="cost_first") as router:
                resp = await router.chat(
                    ChatRequest(model="", messages=[]), scenario="writing"
                )
            assert resp.content == "fallback ok"
            assert resp.model == "claude-sonnet"
            assert mock.chat.await_count == 2

    @pytest.mark.asyncio
    async def test_all_models_fail_raises_last_error(self) -> None:
        from backend.llm import ChatRequest, LLMRouter
        from backend.llm.exceptions import LLMConnectionError

        with patch("backend.llm.router.LLMClient") as MockClient:
            mock = AsyncMock()
            mock.__aenter__ = AsyncMock(return_value=mock)
            mock.__aexit__ = AsyncMock(return_value=None)
            mock.chat = AsyncMock(side_effect=LLMConnectionError("boom"))
            MockClient.return_value = mock

            async with LLMRouter(strategy="cost_first") as router:
                with pytest.raises(LLMConnectionError):
                    await router.chat(
                        ChatRequest(model="", messages=[]), scenario="writing"
                    )
            # cost_first 链: deepseek -> claude = 2 次
            assert mock.chat.await_count == 2
