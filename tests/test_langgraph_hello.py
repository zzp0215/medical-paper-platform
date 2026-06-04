"""
LangGraph Hello World 测试 (mocked, 不连真 LLM).

覆盖
----
- 状态定义合法
- 节点函数返回正确的 partial state
- 条件路由正确分流
- 完整 graph.ainvoke 跑通 (mock LLM)
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

pytestmark = pytest.mark.unit


# ============================================
# 状态 & 节点
# ============================================
class TestStateAndNodes:
    """状态 / 节点单元."""

    def test_state_keys(self) -> None:
        from examples.hello_langgraph import HelloState

        # TypedDict 字段
        annotations = HelloState.__annotations__
        assert "question" in annotations
        assert "thought" in annotations
        assert "answer" in annotations

    def test_conditional_routing_first_iteration(self) -> None:
        from examples.hello_langgraph import should_refine

        state = {"iterations": 0, "max_iterations": 1}
        assert should_refine(state) == "refine"

    def test_conditional_routing_after_max(self) -> None:
        from examples.hello_langgraph import should_refine

        state = {"iterations": 1, "max_iterations": 1}
        assert should_refine(state) == "finalize"


# ============================================
# Graph 集成 (mocked LLM)
# ============================================
class TestGraphIntegration:
    """完整 graph 跑通 (mock LLM)."""

    @pytest.mark.asyncio
    async def test_graph_runs_end_to_end(self) -> None:
        """用 mock LLM 跑通 think → refine → finalize 链路."""
        from examples.hello_langgraph import build_graph
        from backend.llm import ChatResponse, TokenUsage

        with patch("examples.hello_langgraph.LLMRouter") as MockRouter:
            mock = AsyncMock()
            mock.__aenter__ = AsyncMock(return_value=mock)
            mock.__aexit__ = AsyncMock(return_value=None)
            # 第一次: think; 第二次: refine
            mock.chat = AsyncMock(
                side_effect=[
                    ChatResponse(
                        id="r1", model="deepseek-chat",
                        content="2 型糖尿病是成人发病的慢性代谢病",
                        usage=TokenUsage(total_tokens=30, model="deepseek-chat"),
                    ),
                    ChatResponse(
                        id="r2", model="claude-sonnet",
                        content="2 型糖尿病 (T2DM) 是以胰岛素抵抗和分泌不足为特征的代谢性疾病",
                        usage=TokenUsage(total_tokens=50, model="claude-sonnet"),
                    ),
                ]
            )
            MockRouter.return_value = mock

            graph = build_graph()
            result = await graph.ainvoke(
                {"question": "什么是 2 型糖尿病?", "iterations": 0, "max_iterations": 1}
            )

            assert result["thought"] == "2 型糖尿病是成人发病的慢性代谢病"
            assert "T2DM" in result["answer"]
            assert mock.chat.await_count == 2  # think + refine

    @pytest.mark.asyncio
    async def test_graph_max_iterations_zero_skips_refine(self) -> None:
        """max_iterations=0 时, think 后直接 finalize."""
        from examples.hello_langgraph import build_graph
        from backend.llm import ChatResponse, TokenUsage

        with patch("examples.hello_langgraph.LLMRouter") as MockRouter:
            mock = AsyncMock()
            mock.__aenter__ = AsyncMock(return_value=mock)
            mock.__aexit__ = AsyncMock(return_value=None)
            mock.chat = AsyncMock(
                return_value=ChatResponse(
                    id="r1", model="deepseek-chat",
                    content="简短答案",
                    usage=TokenUsage(total_tokens=10, model="deepseek-chat"),
                )
            )
            MockRouter.return_value = mock

            graph = build_graph()
            result = await graph.ainvoke(
                {"question": "test", "iterations": 0, "max_iterations": 0}
            )

            assert result["thought"] == "简短答案"
            # max_iter=0 → 走 finalize, 不调 refine
            assert mock.chat.await_count == 1
            assert "简短答案" in result["answer"]
